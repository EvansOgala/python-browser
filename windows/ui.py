from __future__ import annotations

import html
import os
import shutil
import sys
import urllib.parse
from pathlib import Path

import gi

try:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gdk, GLib, Gtk, WebKit
except Exception as exc:
    raise ImportError(
        "Python Browser requires GTK4 + WebKit 6.0 GI bindings.\n"
        "Install: sudo pacman -S webkitgtk-6.0 python-gobject libsoup3\n"
        "Also make sure no WebKit2 (GTK3 namespace) is imported in this process."
    ) from exc

from gtk_style import install_material_smooth_css
from storage import BrowserStorage


class PythonBrowserApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.evans.PythonBrowser")
        self.window: Gtk.ApplicationWindow | None = None

        self.storage = BrowserStorage()
        self.profile_name = self.storage.current_profile_name()

        self.css_provider = None
        self.network_session: WebKit.NetworkSession | None = None
        self.tab_counter = 0

        self.sidebar_notebook: Gtk.Notebook | None = None
        self.tabs_notebook: Gtk.Notebook | None = None
        self.address_entry: Gtk.Entry | None = None
        self.status_label: Gtk.Label | None = None

        self.profile_dropdown: Gtk.DropDown | None = None
        self.profile_names: list[str] = []

        self.back_btn: Gtk.Button | None = None
        self.forward_btn: Gtk.Button | None = None
        self.reload_btn: Gtk.Button | None = None
        self.stop_btn: Gtk.Button | None = None
        self.bookmark_btn: Gtk.Button | None = None

        self.history_list: Gtk.ListBox | None = None
        self.bookmark_list: Gtk.ListBox | None = None

        self.tab_meta: dict[str, dict] = {}
        self.history_row_url: dict[str, str] = {}
        self.bookmark_row_url: dict[str, str] = {}

    def do_activate(self):
        if self.window is None:
            self._build_ui()
            self._switch_profile(self.profile_name, restore_session=True)
        self.window.present()

    def _build_ui(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("Python Browser")
        self.window.set_default_size(1420, 920)
        self.window.connect("close-request", self._on_close_request)

        self.css_provider = install_material_smooth_css(self.window)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(10)
        root.set_margin_bottom(10)
        root.set_margin_start(10)
        root.set_margin_end(10)
        self.window.set_child(root)

        title = Gtk.Label(label="Python Browser")
        title.set_xalign(0.0)
        title.add_css_class("title-2")
        root.append(title)

        subtitle = Gtk.Label(label="GTK4 browser with tabs, profiles, history, bookmarks, and persistent sign-ins")
        subtitle.set_xalign(0.0)
        subtitle.add_css_class("dim-label")
        root.append(subtitle)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        root.append(toolbar)

        self.back_btn = Gtk.Button(label="←")
        self.back_btn.connect("clicked", lambda _b: self._go_back())
        toolbar.append(self.back_btn)

        self.forward_btn = Gtk.Button(label="→")
        self.forward_btn.connect("clicked", lambda _b: self._go_forward())
        toolbar.append(self.forward_btn)

        self.reload_btn = Gtk.Button(label="⟳")
        self.reload_btn.connect("clicked", lambda _b: self._reload())
        toolbar.append(self.reload_btn)

        self.stop_btn = Gtk.Button(label="✕")
        self.stop_btn.connect("clicked", lambda _b: self._stop())
        toolbar.append(self.stop_btn)

        home_btn = Gtk.Button(label="Home")
        home_btn.connect("clicked", lambda _b: self._go_home())
        toolbar.append(home_btn)

        new_tab_btn = Gtk.Button(label="+ Tab")
        new_tab_btn.connect("clicked", lambda _b: self._create_tab("browser://home", switch=True))
        toolbar.append(new_tab_btn)

        close_tab_btn = Gtk.Button(label="− Tab")
        close_tab_btn.connect("clicked", lambda _b: self._close_current_tab())
        toolbar.append(close_tab_btn)

        self.address_entry = Gtk.Entry()
        self.address_entry.set_hexpand(True)
        self.address_entry.set_placeholder_text("Enter URL or search query")
        self.address_entry.connect("activate", self._on_address_activate)
        toolbar.append(self.address_entry)

        go_btn = Gtk.Button(label="Go")
        go_btn.connect("clicked", lambda _b: self._navigate_from_entry())
        toolbar.append(go_btn)

        self.bookmark_btn = Gtk.Button(label="☆")
        self.bookmark_btn.connect("clicked", lambda _b: self._bookmark_current_page())
        toolbar.append(self.bookmark_btn)

        refresh_lists_btn = Gtk.Button(label="Refresh Lists")
        refresh_lists_btn.connect("clicked", lambda _b: self._refresh_side_lists())
        toolbar.append(refresh_lists_btn)

        add_profile_btn = Gtk.Button(label="+ Profile")
        add_profile_btn.connect("clicked", lambda _b: self._add_profile())
        toolbar.append(add_profile_btn)

        self.profile_dropdown = Gtk.DropDown.new_from_strings(["Default"])
        self.profile_dropdown.connect("notify::selected", self._on_profile_changed)
        toolbar.append(self.profile_dropdown)

        body = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        body.set_hexpand(True)
        body.set_vexpand(True)
        root.append(body)

        self.sidebar_notebook = Gtk.Notebook()
        self.sidebar_notebook.set_size_request(330, -1)
        body.set_start_child(self.sidebar_notebook)

        self.sidebar_notebook.append_page(self._build_history_panel(), Gtk.Label(label="History"))
        self.sidebar_notebook.append_page(self._build_bookmarks_panel(), Gtk.Label(label="Bookmarks"))

        self.tabs_notebook = Gtk.Notebook()
        self.tabs_notebook.set_scrollable(True)
        self.tabs_notebook.connect("switch-page", self._on_switch_page)
        body.set_end_child(self.tabs_notebook)

        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_xalign(0.0)
        self.status_label.add_css_class("dim-label")
        root.append(self.status_label)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(key_controller)

        self._refresh_profile_dropdown(selected=self.profile_name)

    def _build_history_panel(self) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        panel.set_margin_top(8)
        panel.set_margin_bottom(8)
        panel.set_margin_start(8)
        panel.set_margin_end(8)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        panel.append(top)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.connect("clicked", lambda _b: self._clear_history())
        top.append(clear_btn)

        open_btn = Gtk.Button(label="Open")
        open_btn.connect("clicked", lambda _b: self._open_selected_history())
        top.append(open_btn)

        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        panel.append(scroller)

        self.history_list = Gtk.ListBox()
        self.history_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.history_list.connect("row-activated", self._on_history_activated)
        scroller.set_child(self.history_list)

        return panel

    def _build_bookmarks_panel(self) -> Gtk.Widget:
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        panel.set_margin_top(8)
        panel.set_margin_bottom(8)
        panel.set_margin_start(8)
        panel.set_margin_end(8)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        panel.append(top)

        add_btn = Gtk.Button(label="Add Current")
        add_btn.connect("clicked", lambda _b: self._bookmark_current_page())
        top.append(add_btn)

        remove_btn = Gtk.Button(label="Remove")
        remove_btn.connect("clicked", lambda _b: self._remove_selected_bookmark())
        top.append(remove_btn)

        open_btn = Gtk.Button(label="Open")
        open_btn.connect("clicked", lambda _b: self._open_selected_bookmark())
        top.append(open_btn)

        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        panel.append(scroller)

        self.bookmark_list = Gtk.ListBox()
        self.bookmark_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.bookmark_list.connect("row-activated", self._on_bookmark_activated)
        scroller.set_child(self.bookmark_list)

        return panel

    def _set_status(self, text: str):
        if self.status_label is not None:
            self.status_label.set_text(text)

    def _refresh_profile_dropdown(self, selected: str | None = None):
        if self.profile_dropdown is None:
            return
        self.profile_names = self.storage.profile_names()
        if not self.profile_names:
            self.profile_names = ["Default"]

        model = Gtk.StringList.new(self.profile_names)
        self.profile_dropdown.set_model(model)

        target = selected or self.profile_name
        try:
            idx = self.profile_names.index(target)
        except ValueError:
            idx = 0
        self.profile_dropdown.set_selected(idx)

    def _on_profile_changed(self, dropdown: Gtk.DropDown, _param):
        idx = int(dropdown.get_selected())
        if not (0 <= idx < len(self.profile_names)):
            return
        name = self.profile_names[idx]
        if name == self.profile_name:
            return
        self._switch_profile(name, restore_session=True)

    def _add_profile(self):
        name = self._prompt_text("Add Profile", "Profile name")
        if not name:
            return
        try:
            profile = self.storage.add_profile(name)
        except ValueError as exc:
            self._alert("Profile", str(exc))
            return

        self._refresh_profile_dropdown(selected=profile["name"])
        self._switch_profile(profile["name"], restore_session=True)

    def _switch_profile(self, name: str, restore_session: bool):
        self._save_session()

        self.profile_name = name
        self.storage.set_current_profile(name)
        self._configure_web_context(name)

        self._clear_tabs()

        session = self.storage.load_session(name) if restore_session else {"tabs": ["browser://home"], "current_index": 0}
        tabs = session.get("tabs", ["browser://home"]) or ["browser://home"]

        for uri in tabs:
            self._create_tab(uri, switch=False, save_session=False)

        if self.tabs_notebook is not None:
            idx = int(session.get("current_index", 0))
            idx = max(0, min(self.tabs_notebook.get_n_pages() - 1, idx))
            self.tabs_notebook.set_current_page(idx)

        self._refresh_side_lists()
        self._sync_url_and_buttons()
        self._set_status(f"Using profile: {name}")

    def _configure_web_context(self, profile_name: str):
        profile_dir = self.storage.profile_dir(profile_name)
        data_dir = profile_dir / "webkit-data"
        cache_dir = profile_dir / "webkit-cache"
        data_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        session = WebKit.NetworkSession.new(str(data_dir), str(cache_dir))
        session.connect("download-started", self._on_download_started)

        cookie_manager = session.get_cookie_manager()
        cookie_manager.set_persistent_storage(
            str(profile_dir / "cookies.sqlite"),
            WebKit.CookiePersistentStorage.SQLITE,
        )
        if hasattr(session, "set_persistent_credential_storage_enabled"):
            session.set_persistent_credential_storage_enabled(True)

        self.network_session = session

    def _create_tab(self, uri: str = "browser://home", switch: bool = True, save_session: bool = True) -> WebKit.WebView | None:
        if self.tabs_notebook is None or self.network_session is None:
            return None

        webview = WebKit.WebView(network_session=self.network_session)
        settings = webview.get_settings()
        if settings is not None:
            debug_mode = os.environ.get("PYTHON_BROWSER_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
            settings.set_property("enable-back-forward-navigation-gestures", True)
            settings.set_property("enable-developer-extras", debug_mode)
            settings.set_property("javascript-can-open-windows-automatically", True)
            settings.set_property("enable-write-console-messages-to-stdout", debug_mode)

        webview.connect("notify::title", self._on_webview_title_changed)
        webview.connect("notify::uri", self._on_webview_uri_changed)
        webview.connect("load-changed", self._on_webview_load_changed)
        webview.connect("load-failed", self._on_webview_load_failed)
        webview.connect("create", self._on_webview_create)

        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_child(webview)

        tab_key = f"tab-{self.tab_counter}"
        self.tab_counter += 1
        scroller.set_name(tab_key)

        tab_label = Gtk.Label(label="New Tab")
        tab_label.set_ellipsize(3)
        tab_label.set_max_width_chars(24)
        tab_label.set_selectable(False)

        close_btn = Gtk.Button(label="×")
        close_btn.set_size_request(28, 28)
        close_btn.connect("clicked", lambda _b, page=scroller: self._close_tab(page))

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header.append(tab_label)
        header.append(close_btn)

        page_num = self.tabs_notebook.append_page(scroller, header)

        self.tab_meta[tab_key] = {
            "webview": webview,
            "label": tab_label,
            "header": header,
            "page": scroller,
        }

        if switch:
            self.tabs_notebook.set_current_page(page_num)

        self._load_uri_or_home(webview, uri)

        if save_session:
            self._save_session()

        return webview

    def _clear_tabs(self):
        if self.tabs_notebook is None:
            return
        while self.tabs_notebook.get_n_pages() > 0:
            page = self.tabs_notebook.get_nth_page(0)
            self.tabs_notebook.remove_page(0)
            if page is not None:
                self.tab_meta.pop(page.get_name() or "", None)

    def _close_current_tab(self):
        webview = self._current_webview()
        if webview is None:
            return
        page = self._page_for_webview(webview)
        if page is not None:
            self._close_tab(page)

    def _close_tab(self, page: Gtk.Widget):
        if self.tabs_notebook is None:
            return
        index = self.tabs_notebook.page_num(page)
        if index < 0:
            return

        self.tabs_notebook.remove_page(index)
        self.tab_meta.pop(page.get_name() or "", None)

        if self.tabs_notebook.get_n_pages() == 0:
            self._create_tab("browser://home", switch=True, save_session=False)

        self._save_session()
        self._sync_url_and_buttons()

    def _on_switch_page(self, _notebook: Gtk.Notebook, _page: Gtk.Widget, _index: int):
        self._sync_url_and_buttons()

    def _on_webview_create(self, _webview: WebKit.WebView, _navigation_action):
        new_webview = self._create_tab("browser://home", switch=True)
        return new_webview

    def _on_webview_title_changed(self, webview: WebKit.WebView, _param):
        title = (webview.get_title() or webview.get_uri() or "New Tab").strip() or "New Tab"
        meta = self._meta_for_webview(webview)
        if meta is not None:
            label = meta["label"]
            label.set_text(title[:80])

        if webview == self._current_webview() and self.window is not None:
            self.window.set_title(f"{title} - Python Browser")

    def _on_webview_uri_changed(self, webview: WebKit.WebView, _param):
        if webview == self._current_webview() and self.address_entry is not None:
            uri = webview.get_uri() or ""
            if not uri.startswith("browser://"):
                self.address_entry.set_text(uri)
            else:
                self.address_entry.set_text("")
        self._sync_nav_buttons()

    def _on_webview_load_changed(self, webview: WebKit.WebView, event: WebKit.LoadEvent):
        if event == WebKit.LoadEvent.STARTED:
            self._set_status("Loading...")
        elif event == WebKit.LoadEvent.FINISHED:
            uri = webview.get_uri() or ""
            title = webview.get_title() or uri
            self._set_status("Done")
            if uri and not uri.startswith("browser://"):
                self.storage.add_history(self.profile_name, uri, title)
                self._refresh_history_list()
            self._save_session()
            self._sync_bookmark_button()

    def _on_webview_load_failed(self, _webview, _event, failing_uri, error):
        self._set_status(f"Load failed: {failing_uri} ({error.message})")
        return False

    def _on_address_activate(self, _entry: Gtk.Entry):
        self._navigate_from_entry()

    def _navigate_from_entry(self):
        if self.address_entry is None:
            return
        text = self.address_entry.get_text().strip()
        webview = self._current_webview()
        if webview is None:
            webview = self._create_tab("browser://home", switch=True)
        if webview is None:
            return

        uri = self._resolve_input_to_uri(text)
        self._load_uri_or_home(webview, uri)

    def _resolve_input_to_uri(self, text: str) -> str:
        value = (text or "").strip()
        if not value:
            return "browser://home"

        if value.startswith("browser://"):
            return value

        if "://" in value:
            return value

        if " " in value:
            return self._search_uri(value)

        if value.startswith("localhost") or "." in value:
            return f"https://{value}"

        return self._search_uri(value)

    def _search_uri(self, query: str) -> str:
        profile = self.storage.get_profile(self.profile_name)
        template = profile.get("search_url", "https://duckduckgo.com/?q={query}")
        encoded = urllib.parse.quote_plus(query)
        return template.replace("{query}", encoded)

    def _go_home(self):
        webview = self._current_webview()
        if webview is None:
            webview = self._create_tab("browser://home", switch=True)
        if webview is None:
            return
        self._load_uri_or_home(webview, "browser://home")

    def _go_back(self):
        webview = self._current_webview()
        if webview and webview.can_go_back():
            webview.go_back()

    def _go_forward(self):
        webview = self._current_webview()
        if webview and webview.can_go_forward():
            webview.go_forward()

    def _reload(self):
        webview = self._current_webview()
        if webview:
            webview.reload()

    def _stop(self):
        webview = self._current_webview()
        if webview:
            webview.stop_loading()

    def _current_webview(self) -> WebKit.WebView | None:
        if self.tabs_notebook is None:
            return None
        index = self.tabs_notebook.get_current_page()
        if index < 0:
            return None
        page = self.tabs_notebook.get_nth_page(index)
        if page is None:
            return None
        meta = self.tab_meta.get(page.get_name() or "")
        if meta is None:
            return None
        return meta.get("webview")

    def _page_for_webview(self, webview: WebKit.WebView) -> Gtk.Widget | None:
        for meta in self.tab_meta.values():
            if meta.get("webview") == webview:
                return meta.get("page")
        return None

    def _meta_for_webview(self, webview: WebKit.WebView) -> dict | None:
        for meta in self.tab_meta.values():
            if meta.get("webview") == webview:
                return meta
        return None

    def _load_uri_or_home(self, webview: WebKit.WebView, uri: str):
        target = (uri or "").strip() or "browser://home"
        if target.startswith("browser://home"):
            webview.load_html(self._build_home_page_html(), "browser://home/")
            return
        webview.load_uri(target)

    def _build_home_page_html(self) -> str:
        bookmarks = self.storage.list_bookmarks(self.profile_name)[:8]
        history = self.storage.recent_history(self.profile_name, limit=8)

        def card_link(url: str, title: str) -> str:
            return (
                "<a class='chip' href='" + html.escape(url) + "'>"
                + html.escape(title)
                + "</a>"
            )

        bookmark_html = "".join(card_link(b["url"], b.get("title") or b["url"]) for b in bookmarks) or "<p>No bookmarks yet.</p>"
        history_html = "".join(card_link(h["url"], h.get("title") or h["url"]) for h in history) or "<p>No history yet.</p>"

        return f"""
<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Home</title>
<style>
:root {{
  color-scheme: light dark;
}}
body {{
  font-family: Cantarell, sans-serif;
  margin: 0;
  padding: 28px;
  background: radial-gradient(circle at top, rgba(80,80,80,0.2), transparent 42%), transparent;
}}
.container {{ max-width: 980px; margin: 0 auto; }}
.hero {{ padding: 12px 0 6px; }}
.hero h1 {{ margin: 0; font-size: 2rem; }}
.hero p {{ opacity: 0.8; margin: 0.4rem 0 0; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px; }}
.card {{ border-radius: 18px; padding: 14px; border: 1px solid rgba(128,128,128,0.3); background: rgba(128,128,128,0.08); }}
.card h2 {{ margin-top: 0; font-size: 1.05rem; }}
.chip {{ display: inline-block; margin: 4px 6px 4px 0; padding: 8px 12px; border-radius: 999px; text-decoration: none; border: 1px solid rgba(128,128,128,0.35); }}
.quick a {{ display: inline-block; margin: 6px 8px 0 0; padding: 10px 14px; border-radius: 999px; text-decoration: none; border: 1px solid rgba(128,128,128,0.45); }}
@media (max-width: 880px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
  <div class='container'>
    <section class='hero'>
      <h1>Welcome, {html.escape(self.profile_name)}</h1>
      <p>Your local-first GTK browser. Data stays in <code>~/.local/share/python-browser</code>.</p>
    </section>

    <section class='quick'>
      {card_link('https://www.google.com', 'Google')}
      {card_link('https://duckduckgo.com', 'DuckDuckGo')}
      {card_link('https://github.com', 'GitHub')}
      {card_link('https://news.ycombinator.com', 'Hacker News')}
      {card_link('https://mail.google.com', 'Gmail')}
      {card_link('https://calendar.google.com', 'Calendar')}
    </section>

    <section class='grid'>
      <article class='card'>
        <h2>Bookmarks</h2>
        {bookmark_html}
      </article>
      <article class='card'>
        <h2>Recent History</h2>
        {history_html}
      </article>
    </section>
  </div>
</body>
</html>
"""

    def _refresh_side_lists(self):
        self._refresh_history_list()
        self._refresh_bookmark_list()

    def _refresh_history_list(self):
        if self.history_list is None:
            return
        self._clear_listbox(self.history_list)
        self.history_row_url.clear()

        history = self.storage.recent_history(self.profile_name, limit=300)
        for i, item in enumerate(history):
            title = (item.get("title") or item.get("url") or "(untitled)").strip()
            url = (item.get("url") or "").strip()
            if not url:
                continue
            row = Gtk.ListBoxRow()
            row_key = f"history-{i}"
            row.set_name(row_key)
            row.set_child(Gtk.Label(label=f"{title}\n{url}", xalign=0.0, wrap=True))
            self.history_row_url[row_key] = url
            self.history_list.append(row)

    def _refresh_bookmark_list(self):
        if self.bookmark_list is None:
            return
        self._clear_listbox(self.bookmark_list)
        self.bookmark_row_url.clear()

        bookmarks = self.storage.list_bookmarks(self.profile_name)
        for i, item in enumerate(bookmarks):
            title = (item.get("title") or item.get("url") or "(untitled)").strip()
            url = (item.get("url") or "").strip()
            if not url:
                continue
            row = Gtk.ListBoxRow()
            row_key = f"bookmark-{i}"
            row.set_name(row_key)
            row.set_child(Gtk.Label(label=f"{title}\n{url}", xalign=0.0, wrap=True))
            self.bookmark_row_url[row_key] = url
            self.bookmark_list.append(row)

        self._sync_bookmark_button()

    def _on_history_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow):
        url = self.history_row_url.get(row.get_name() or "")
        if not url:
            return
        webview = self._current_webview() or self._create_tab("browser://home", switch=True)
        if webview:
            webview.load_uri(url)

    def _on_bookmark_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow):
        url = self.bookmark_row_url.get(row.get_name() or "")
        if not url:
            return
        webview = self._current_webview() or self._create_tab("browser://home", switch=True)
        if webview:
            webview.load_uri(url)

    def _open_selected_history(self):
        if self.history_list is None:
            return
        row = self.history_list.get_selected_row()
        if row is not None:
            self._on_history_activated(self.history_list, row)

    def _open_selected_bookmark(self):
        if self.bookmark_list is None:
            return
        row = self.bookmark_list.get_selected_row()
        if row is not None:
            self._on_bookmark_activated(self.bookmark_list, row)

    def _clear_history(self):
        self.storage.clear_history(self.profile_name)
        self._refresh_history_list()
        self._set_status("History cleared")

    def _bookmark_current_page(self):
        webview = self._current_webview()
        if webview is None:
            return
        url = webview.get_uri() or ""
        if not url or url.startswith("browser://"):
            self._set_status("No page URL to bookmark")
            return
        title = webview.get_title() or url
        self.storage.add_bookmark(self.profile_name, title, url)
        self._refresh_bookmark_list()
        self._set_status("Bookmarked")

    def _remove_selected_bookmark(self):
        if self.bookmark_list is None:
            return
        row = self.bookmark_list.get_selected_row()
        if row is None:
            self._set_status("Select a bookmark first")
            return
        url = self.bookmark_row_url.get(row.get_name() or "")
        if not url:
            return
        self.storage.remove_bookmark(self.profile_name, url)
        self._refresh_bookmark_list()
        self._set_status("Bookmark removed")

    def _sync_bookmark_button(self):
        if self.bookmark_btn is None:
            return
        webview = self._current_webview()
        if webview is None:
            self.bookmark_btn.set_label("☆")
            return
        uri = webview.get_uri() or ""
        bookmarked = any(b.get("url") == uri for b in self.storage.list_bookmarks(self.profile_name))
        self.bookmark_btn.set_label("★" if bookmarked else "☆")

    def _save_session(self):
        if self.tabs_notebook is None:
            return

        tabs: list[str] = []
        for i in range(self.tabs_notebook.get_n_pages()):
            page = self.tabs_notebook.get_nth_page(i)
            if page is None:
                continue
            meta = self.tab_meta.get(page.get_name() or "")
            if meta is None:
                continue
            webview = meta.get("webview")
            uri = webview.get_uri() if webview is not None else None
            tabs.append(uri or "browser://home")

        current_index = max(0, self.tabs_notebook.get_current_page())
        self.storage.save_session(self.profile_name, tabs, current_index)

    def _sync_url_and_buttons(self):
        webview = self._current_webview()
        if self.address_entry is not None:
            if webview is None:
                self.address_entry.set_text("")
            else:
                uri = webview.get_uri() or ""
                self.address_entry.set_text("" if uri.startswith("browser://") else uri)
        self._sync_nav_buttons()
        self._sync_bookmark_button()

    def _sync_nav_buttons(self):
        webview = self._current_webview()
        can_back = bool(webview and webview.can_go_back())
        can_forward = bool(webview and webview.can_go_forward())
        if self.back_btn is not None:
            self.back_btn.set_sensitive(can_back)
        if self.forward_btn is not None:
            self.forward_btn.set_sensitive(can_forward)
        if self.reload_btn is not None:
            self.reload_btn.set_sensitive(webview is not None)
        if self.stop_btn is not None:
            self.stop_btn.set_sensitive(webview is not None)

    def _on_download_started(self, _session: WebKit.NetworkSession, download: WebKit.Download):
        download.connect("decide-destination", self._on_decide_download_destination)
        download.connect("finished", lambda _d: self._set_status("Download finished"))
        download.connect("failed", lambda _d, _err: self._set_status("Download failed"))

    def _on_decide_download_destination(self, download: WebKit.Download, suggested_filename: str) -> bool:
        downloads_dir = Path.home() / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)

        target = downloads_dir / suggested_filename
        stem = target.stem
        suffix = target.suffix
        i = 2
        while target.exists():
            target = downloads_dir / f"{stem}-{i}{suffix}"
            i += 1

        download.set_destination(target.as_uri())
        self._set_status(f"Downloading: {target.name}")
        return True

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if not ctrl:
            return False

        if keyval in (Gdk.KEY_l, Gdk.KEY_L):
            if self.address_entry is not None:
                self.address_entry.grab_focus()
                self.address_entry.select_region(0, -1)
            return True

        if keyval in (Gdk.KEY_t, Gdk.KEY_T):
            self._create_tab("browser://home", switch=True)
            return True

        if keyval in (Gdk.KEY_w, Gdk.KEY_W):
            self._close_current_tab()
            return True

        if keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self._reload()
            return True

        if keyval in (Gdk.KEY_h, Gdk.KEY_H):
            self._go_home()
            return True

        return False

    def _on_close_request(self, _window):
        self._save_session()
        return False

    def _alert(self, title: str, message: str):
        if self.window is None:
            return
        dialog = Gtk.Dialog(title=title, transient_for=self.window, modal=True)
        dialog.add_button("OK", Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        label = Gtk.Label(label=message)
        label.set_wrap(True)
        label.set_xalign(0.0)
        label.set_margin_top(12)
        label.set_margin_bottom(12)
        label.set_margin_start(12)
        label.set_margin_end(12)
        content.append(label)
        self._run_dialog(dialog)

    def _prompt_text(self, title: str, prompt: str, initial: str = "") -> str | None:
        if self.window is None:
            return None

        dialog = Gtk.Dialog(title=title, transient_for=self.window, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("OK", Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        content.append(box)

        label = Gtk.Label(label=prompt)
        label.set_xalign(0.0)
        box.append(label)

        entry = Gtk.Entry()
        entry.set_text(initial)
        box.append(entry)

        response = self._run_dialog(dialog, focus_entry=entry)
        if response != Gtk.ResponseType.OK:
            return None

        value = entry.get_text().strip()
        return value or None

    def _run_dialog(self, dialog: Gtk.Dialog, focus_entry: Gtk.Entry | None = None):
        loop = GLib.MainLoop()
        result = {"response": Gtk.ResponseType.CANCEL}

        def on_response(_dialog, response_id):
            result["response"] = response_id
            dialog.destroy()
            loop.quit()

        dialog.connect("response", on_response)
        dialog.present()
        if focus_entry is not None:
            focus_entry.grab_focus()
        loop.run()
        return result["response"]

    @staticmethod
    def _clear_listbox(box: Gtk.ListBox):
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
