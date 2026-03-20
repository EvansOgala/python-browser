from __future__ import annotations

import html
import os
import sys
import urllib.parse
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from storage import BrowserStorage


class BrowserPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, app: "PythonBrowserQtWindow"):
        super().__init__(profile)
        self.app = app

    def createWindow(self, _type):
        return self.app._create_tab("browser://home", switch=True)


class PythonBrowserQtWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Browser")
        self.resize(1420, 920)

        self.storage = BrowserStorage()
        self.profile_name = self.storage.current_profile_name()
        self.profile_names: list[str] = []
        self.qt_profile: QWebEngineProfile | None = None
        self._suppress_profile_change = False

        self.history_row_url: dict[int, str] = {}
        self.bookmark_row_url: dict[int, str] = {}

        self._build_ui()
        self._refresh_profile_dropdown()
        self._switch_profile(self.profile_name, restore_session=True)

    def _build_ui(self):
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(8)

        self.title_label = QtWidgets.QLabel("Python Browser")
        self.title_label.setStyleSheet("font-size: 26px; font-weight: 700;")
        self.subtitle_label = QtWidgets.QLabel("Tabbed browser with profiles, bookmarks, history, and persistent sessions")
        outer.addWidget(self.title_label)
        outer.addWidget(self.subtitle_label)

        toolbar = QtWidgets.QHBoxLayout()
        outer.addLayout(toolbar)

        self.back_btn = QtWidgets.QPushButton("←")
        self.back_btn.clicked.connect(self._go_back)
        toolbar.addWidget(self.back_btn)

        self.forward_btn = QtWidgets.QPushButton("→")
        self.forward_btn.clicked.connect(self._go_forward)
        toolbar.addWidget(self.forward_btn)

        self.reload_btn = QtWidgets.QPushButton("↻")
        self.reload_btn.clicked.connect(self._reload)
        toolbar.addWidget(self.reload_btn)

        self.stop_btn = QtWidgets.QPushButton("✕")
        self.stop_btn.clicked.connect(self._stop)
        toolbar.addWidget(self.stop_btn)

        home_btn = QtWidgets.QPushButton("Home")
        home_btn.clicked.connect(self._go_home)
        toolbar.addWidget(home_btn)

        new_tab_btn = QtWidgets.QPushButton("+ Tab")
        new_tab_btn.clicked.connect(lambda: self._create_tab("browser://home", switch=True))
        toolbar.addWidget(new_tab_btn)

        close_tab_btn = QtWidgets.QPushButton("− Tab")
        close_tab_btn.clicked.connect(self._close_current_tab)
        toolbar.addWidget(close_tab_btn)

        self.address_entry = QtWidgets.QLineEdit()
        self.address_entry.setPlaceholderText("Enter URL or search query")
        self.address_entry.returnPressed.connect(self._navigate_from_entry)
        toolbar.addWidget(self.address_entry, 1)

        go_btn = QtWidgets.QPushButton("Go")
        go_btn.clicked.connect(self._navigate_from_entry)
        toolbar.addWidget(go_btn)

        self.bookmark_btn = QtWidgets.QPushButton("☆")
        self.bookmark_btn.clicked.connect(self._bookmark_current_page)
        toolbar.addWidget(self.bookmark_btn)

        refresh_lists_btn = QtWidgets.QPushButton("Refresh Lists")
        refresh_lists_btn.clicked.connect(self._refresh_side_lists)
        toolbar.addWidget(refresh_lists_btn)

        add_profile_btn = QtWidgets.QPushButton("+ Profile")
        add_profile_btn.clicked.connect(self._add_profile)
        toolbar.addWidget(add_profile_btn)

        self.profile_box = QtWidgets.QComboBox()
        self.profile_box.currentIndexChanged.connect(self._on_profile_changed)
        toolbar.addWidget(self.profile_box)

        self.engine_label = QtWidgets.QLabel("Engine")
        toolbar.addWidget(self.engine_label)

        self.engine_box = QtWidgets.QComboBox()
        self.engine_box.addItem("PySide (Full UI)", "pyside")
        self.engine_box.addItem("WebView2 (Compat)", "webview2")
        current_engine = self.storage.preferred_engine()
        idx = self.engine_box.findData(current_engine)
        self.engine_box.setCurrentIndex(idx if idx >= 0 else 0)
        toolbar.addWidget(self.engine_box)

        self.apply_engine_btn = QtWidgets.QPushButton("Apply Engine")
        self.apply_engine_btn.clicked.connect(self._apply_engine_setting)
        toolbar.addWidget(self.apply_engine_btn)

        if os.name != "nt":
            self.engine_label.hide()
            self.engine_box.hide()
            self.apply_engine_btn.hide()

        split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)

        side_tabs = QtWidgets.QTabWidget()
        split.addWidget(side_tabs)

        history_tab = QtWidgets.QWidget()
        h_layout = QtWidgets.QVBoxLayout(history_tab)
        h_top = QtWidgets.QHBoxLayout()
        h_layout.addLayout(h_top)
        h_clear = QtWidgets.QPushButton("Clear")
        h_clear.clicked.connect(self._clear_history)
        h_top.addWidget(h_clear)
        h_open = QtWidgets.QPushButton("Open")
        h_open.clicked.connect(self._open_selected_history)
        h_top.addWidget(h_open)
        self.history_list = QtWidgets.QListWidget()
        self.history_list.itemActivated.connect(self._on_history_activated)
        h_layout.addWidget(self.history_list, 1)
        side_tabs.addTab(history_tab, "History")

        bookmarks_tab = QtWidgets.QWidget()
        b_layout = QtWidgets.QVBoxLayout(bookmarks_tab)
        b_top = QtWidgets.QHBoxLayout()
        b_layout.addLayout(b_top)
        b_add = QtWidgets.QPushButton("Add Current")
        b_add.clicked.connect(self._bookmark_current_page)
        b_top.addWidget(b_add)
        b_rm = QtWidgets.QPushButton("Remove")
        b_rm.clicked.connect(self._remove_selected_bookmark)
        b_top.addWidget(b_rm)
        b_open = QtWidgets.QPushButton("Open")
        b_open.clicked.connect(self._open_selected_bookmark)
        b_top.addWidget(b_open)
        self.bookmark_list = QtWidgets.QListWidget()
        self.bookmark_list.itemActivated.connect(self._on_bookmark_activated)
        b_layout.addWidget(self.bookmark_list, 1)
        side_tabs.addTab(bookmarks_tab, "Bookmarks")

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab_index)
        self.tabs.currentChanged.connect(self._on_tab_switched)
        split.addWidget(self.tabs)
        split.setSizes([320, 1080])

        self.status_label = QtWidgets.QLabel("Ready")
        outer.addWidget(self.status_label)

        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self, activated=self._focus_url)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self, activated=lambda: self._create_tab("browser://home", switch=True))
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+W"), self, activated=self._close_current_tab)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, activated=self._reload)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+H"), self, activated=self._go_home)

    def _set_status(self, text: str):
        self.status_label.setText(text)

    def _refresh_profile_dropdown(self):
        self.profile_names = self.storage.profile_names() or ["Default"]
        self._suppress_profile_change = True
        self.profile_box.clear()
        self.profile_box.addItems(self.profile_names)
        idx = self.profile_names.index(self.profile_name) if self.profile_name in self.profile_names else 0
        self.profile_box.setCurrentIndex(idx)
        self._suppress_profile_change = False

    def _on_profile_changed(self, index: int):
        if self._suppress_profile_change:
            return
        if not (0 <= index < len(self.profile_names)):
            return
        name = self.profile_names[index]
        if name == self.profile_name:
            return
        self._switch_profile(name, restore_session=True)

    def _add_profile(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Add Profile", "Profile name")
        if not ok or not name.strip():
            return
        try:
            profile = self.storage.add_profile(name.strip())
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Profile", str(exc))
            return
        self.profile_name = profile["name"]
        self._refresh_profile_dropdown()
        self._switch_profile(self.profile_name, restore_session=True)

    def _apply_engine_setting(self):
        engine = self.engine_box.currentData()
        if not isinstance(engine, str):
            return
        try:
            self.storage.set_preferred_engine(engine)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Engine", str(exc))
            return
        choice = QtWidgets.QMessageBox.question(
            self,
            "Engine Updated",
            "Engine preference saved. Restart now to apply?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes,
        )
        if choice != QtWidgets.QMessageBox.StandardButton.Yes:
            self._set_status(f"Engine saved: {engine}. Restart app to apply.")
            return

        self._save_session()
        script_path = os.path.join(os.path.dirname(__file__), "main.py")
        if getattr(sys, "frozen", False):
            QtCore.QProcess.startDetached(sys.executable, [])
        else:
            QtCore.QProcess.startDetached(sys.executable, [script_path])
        QtWidgets.QApplication.quit()

    def _configure_profile(self, name: str):
        profile_dir = self.storage.profile_dir(name)
        data_dir = profile_dir / "qt-data"
        cache_dir = profile_dir / "qt-cache"
        data_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        profile_slug = self.storage.get_profile(name).get("slug", "default")
        # Use a named profile (without window parent) to improve persistence stability.
        p = QWebEngineProfile(profile_slug)
        p.setPersistentStoragePath(str(data_dir))
        p.setCachePath(str(cache_dir))
        p.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        p.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        p.setPersistentPermissionsPolicy(QWebEngineProfile.PersistentPermissionsPolicy.StoreOnDisk)
        p.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        p.downloadRequested.connect(self._on_download_requested)
        self.qt_profile = p

    def closeEvent(self, event: QtGui.QCloseEvent):
        self._save_session()
        super().closeEvent(event)

    def _switch_profile(self, name: str, restore_session: bool):
        self._save_session()
        self.profile_name = name
        self.storage.set_current_profile(name)
        self._configure_profile(name)
        self._clear_tabs()

        session = self.storage.load_session(name) if restore_session else {"tabs": ["browser://home"], "current_index": 0}
        tabs = session.get("tabs", ["browser://home"]) or ["browser://home"]
        for uri in tabs:
            self._create_tab(uri, switch=False, save_session=False)

        idx = int(session.get("current_index", 0))
        if self.tabs.count() > 0:
            idx = max(0, min(self.tabs.count() - 1, idx))
            self.tabs.setCurrentIndex(idx)

        self._refresh_side_lists()
        self._sync_url_and_buttons()
        if self.qt_profile is not None:
            mode = "off-record" if self.qt_profile.isOffTheRecord() else "persistent"
            storage_path = self.qt_profile.persistentStoragePath() or "(none)"
            self.setWindowTitle(f"Python Browser - {name} [{mode}]")
            self._set_status(f"Profile: {name} | Mode: {mode} | Storage: {storage_path}")
        else:
            self.setWindowTitle(f"Python Browser - {name}")
            self._set_status(f"Using profile: {name}")
        self._refresh_profile_dropdown()

    def _create_tab(self, uri: str = "browser://home", switch: bool = True, save_session: bool = True):
        if self.qt_profile is None:
            return None
        view = QWebEngineView()
        page = BrowserPage(self.qt_profile, self)
        view.setPage(page)
        view.titleChanged.connect(lambda _t, v=view: self._on_title_changed(v))
        view.urlChanged.connect(lambda _u, v=view: self._on_url_changed(v))
        view.loadFinished.connect(lambda _ok, v=view: self._on_load_finished(v))

        index = self.tabs.addTab(view, "New Tab")
        if switch:
            self.tabs.setCurrentIndex(index)
        self._load_uri_or_home(view, uri)
        if save_session:
            self._save_session()
        return page

    def _close_tab_index(self, index: int):
        if index < 0:
            return
        if self.tabs.count() <= 1:
            # Keep one live tab instead of destroying it.
            # Some websites keep auth/session state in tab-scoped storage.
            view = self._view_for_index(index)
            if view is not None:
                self._load_uri_or_home(view, "browser://home")
                self.tabs.setTabText(index, "Home")
                self.tabs.setCurrentIndex(index)
            self._set_status("Reset current tab to Home")
            self._save_session()
            self._sync_url_and_buttons()
            return

        self.tabs.removeTab(index)
        self._save_session()
        self._sync_url_and_buttons()

    def _close_current_tab(self):
        index = self.tabs.currentIndex()
        if index >= 0:
            self._close_tab_index(index)

    def _clear_tabs(self):
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)

    def _current_view(self) -> QWebEngineView | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, QWebEngineView) else None

    def _view_for_index(self, idx: int) -> QWebEngineView | None:
        w = self.tabs.widget(idx)
        return w if isinstance(w, QWebEngineView) else None

    def _on_tab_switched(self, _index: int):
        self._sync_url_and_buttons()

    def _on_title_changed(self, view: QWebEngineView):
        title = (view.title() or "New Tab").strip() or "New Tab"
        idx = self.tabs.indexOf(view)
        if idx >= 0:
            self.tabs.setTabText(idx, title[:40])
        if view == self._current_view():
            self.setWindowTitle(f"{title} - Python Browser")

    def _on_url_changed(self, view: QWebEngineView):
        if view == self._current_view():
            url = view.url().toString()
            self.address_entry.setText("" if url.startswith("browser://") else url)
        self._sync_nav_buttons()

    def _on_load_finished(self, view: QWebEngineView):
        url = view.url().toString()
        title = view.title() or url
        if url and not url.startswith("browser://"):
            self.storage.add_history(self.profile_name, url, title)
            self._refresh_history_list()
        self._save_session()
        self._sync_bookmark_button()
        self._set_status("Done")

    def _resolve_input_to_uri(self, text: str) -> str:
        value = (text or "").strip()
        if not value:
            return "browser://home"
        if value.startswith("browser://") or "://" in value:
            return value
        if " " in value:
            return self._search_uri(value)
        if value.startswith("localhost") or "." in value:
            return f"https://{value}"
        return self._search_uri(value)

    def _search_uri(self, query: str) -> str:
        profile = self.storage.get_profile(self.profile_name)
        template = profile.get("search_url", "https://www.google.com/search?q={query}")
        encoded = urllib.parse.quote_plus(query)
        return template.replace("{query}", encoded)

    def _navigate_from_entry(self):
        view = self._current_view()
        if view is None:
            self._create_tab("browser://home", switch=True)
            view = self._current_view()
        if view is None:
            return
        uri = self._resolve_input_to_uri(self.address_entry.text().strip())
        self._load_uri_or_home(view, uri)

    def _load_uri_or_home(self, view: QWebEngineView, uri: str):
        target = (uri or "").strip() or "browser://home"
        if target.startswith("browser://home"):
            view.setHtml(self._build_home_page_html(), QtCore.QUrl("https://browser.home/"))
            return
        view.setUrl(QtCore.QUrl(target))
        self._set_status("Loading...")

    def _go_back(self):
        view = self._current_view()
        if view is not None:
            view.back()

    def _go_forward(self):
        view = self._current_view()
        if view is not None:
            view.forward()

    def _reload(self):
        view = self._current_view()
        if view is not None:
            view.reload()

    def _stop(self):
        view = self._current_view()
        if view is not None:
            view.stop()

    def _go_home(self):
        view = self._current_view()
        if view is None:
            self._create_tab("browser://home", switch=True)
            return
        self._load_uri_or_home(view, "browser://home")

    def _focus_url(self):
        self.address_entry.setFocus()
        self.address_entry.selectAll()

    def _sync_url_and_buttons(self):
        view = self._current_view()
        if view is None:
            self.address_entry.setText("")
        else:
            url = view.url().toString()
            self.address_entry.setText("" if url.startswith("browser://") else url)
        self._sync_nav_buttons()
        self._sync_bookmark_button()

    def _sync_nav_buttons(self):
        view = self._current_view()
        can_back = bool(view and view.history().canGoBack())
        can_forward = bool(view and view.history().canGoForward())
        self.back_btn.setEnabled(can_back)
        self.forward_btn.setEnabled(can_forward)
        self.reload_btn.setEnabled(view is not None)
        self.stop_btn.setEnabled(view is not None)

    def _save_session(self):
        tabs: list[str] = []
        for i in range(self.tabs.count()):
            view = self._view_for_index(i)
            if view is None:
                continue
            url = view.url().toString()
            tabs.append(url or "browser://home")
        if not tabs:
            tabs = ["browser://home"]
        self.storage.save_session(self.profile_name, tabs, max(0, self.tabs.currentIndex()))

    def _refresh_side_lists(self):
        self._refresh_history_list()
        self._refresh_bookmark_list()

    def _refresh_history_list(self):
        self.history_list.clear()
        self.history_row_url.clear()
        for i, item in enumerate(self.storage.recent_history(self.profile_name, limit=300)):
            title = (item.get("title") or item.get("url") or "(untitled)").strip()
            url = (item.get("url") or "").strip()
            if not url:
                continue
            self.history_list.addItem(f"{title}\n{url}")
            self.history_row_url[self.history_list.count() - 1] = url

    def _refresh_bookmark_list(self):
        self.bookmark_list.clear()
        self.bookmark_row_url.clear()
        for i, item in enumerate(self.storage.list_bookmarks(self.profile_name)):
            title = (item.get("title") or item.get("url") or "(untitled)").strip()
            url = (item.get("url") or "").strip()
            if not url:
                continue
            self.bookmark_list.addItem(f"{title}\n{url}")
            self.bookmark_row_url[self.bookmark_list.count() - 1] = url
        self._sync_bookmark_button()

    def _on_history_activated(self, item: QtWidgets.QListWidgetItem):
        row = self.history_list.row(item)
        url = self.history_row_url.get(row, "")
        if not url:
            return
        view = self._current_view()
        if view is None:
            self._create_tab("browser://home", switch=True)
            view = self._current_view()
        if view is not None:
            view.setUrl(QtCore.QUrl(url))

    def _on_bookmark_activated(self, item: QtWidgets.QListWidgetItem):
        row = self.bookmark_list.row(item)
        url = self.bookmark_row_url.get(row, "")
        if not url:
            return
        view = self._current_view()
        if view is None:
            self._create_tab("browser://home", switch=True)
            view = self._current_view()
        if view is not None:
            view.setUrl(QtCore.QUrl(url))

    def _open_selected_history(self):
        item = self.history_list.currentItem()
        if item:
            self._on_history_activated(item)

    def _open_selected_bookmark(self):
        item = self.bookmark_list.currentItem()
        if item:
            self._on_bookmark_activated(item)

    def _clear_history(self):
        self.storage.clear_history(self.profile_name)
        self._refresh_history_list()
        self._set_status("History cleared")

    def _bookmark_current_page(self):
        view = self._current_view()
        if view is None:
            return
        url = view.url().toString()
        if not url or url.startswith("browser://"):
            self._set_status("No page URL to bookmark")
            return
        title = view.title() or url
        self.storage.add_bookmark(self.profile_name, title, url)
        self._refresh_bookmark_list()
        self._set_status("Bookmarked")

    def _remove_selected_bookmark(self):
        item = self.bookmark_list.currentItem()
        if item is None:
            self._set_status("Select a bookmark first")
            return
        row = self.bookmark_list.row(item)
        url = self.bookmark_row_url.get(row, "")
        if not url:
            return
        self.storage.remove_bookmark(self.profile_name, url)
        self._refresh_bookmark_list()
        self._set_status("Bookmark removed")

    def _sync_bookmark_button(self):
        view = self._current_view()
        if view is None:
            self.bookmark_btn.setText("☆")
            return
        uri = view.url().toString()
        bookmarked = any(b.get("url") == uri for b in self.storage.list_bookmarks(self.profile_name))
        self.bookmark_btn.setText("★" if bookmarked else "☆")

    def _on_download_requested(self, item: QWebEngineDownloadRequest):
        downloads_dir = Path.home() / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)

        suggested = item.downloadFileName() or "download.bin"
        target = downloads_dir / suggested
        stem = target.stem
        suffix = target.suffix
        i = 2
        while target.exists():
            target = downloads_dir / f"{stem}-{i}{suffix}"
            i += 1

        item.setDownloadDirectory(str(downloads_dir))
        item.setDownloadFileName(target.name)
        item.accept()
        self._set_status(f"Downloading: {target.name}")

    def _build_home_page_html(self) -> str:
        bookmarks = self.storage.list_bookmarks(self.profile_name)[:8]
        history = self.storage.recent_history(self.profile_name, limit=8)

        def card_link(url: str, title: str) -> str:
            return "<a class='chip' href='" + html.escape(url) + "'>" + html.escape(title) + "</a>"

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
body {{
  font-family: "Segoe UI", sans-serif;
  margin: 0;
  padding: 28px;
  background: radial-gradient(circle at top, rgba(60,120,255,0.18), transparent 42%), #f3f6fb;
  color: #1a253d;
}}
.container {{ max-width: 980px; margin: 0 auto; }}
.hero h1 {{ margin: 0; font-size: 2rem; }}
.hero p {{ opacity: 0.8; margin: 0.4rem 0 0; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px; }}
.card {{ border-radius: 18px; padding: 14px; border: 1px solid rgba(80,100,140,0.25); background: rgba(255,255,255,0.75); }}
.chip {{ display: inline-block; margin: 4px 6px 4px 0; padding: 8px 12px; border-radius: 999px; text-decoration: none; border: 1px solid rgba(80,100,140,0.35); color: #1a253d; }}
@media (max-width: 880px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
  <div class='container'>
    <section class='hero'>
      <h1>Welcome, {html.escape(self.profile_name)}</h1>
      <p>Your local-first browser profile data is stored on this PC.</p>
    </section>
    <section>
      {card_link('https://www.google.com', 'Google')}
      {card_link('https://duckduckgo.com', 'DuckDuckGo')}
      {card_link('https://github.com', 'GitHub')}
      {card_link('https://news.ycombinator.com', 'Hacker News')}
      {card_link('https://mail.google.com', 'Gmail')}
      {card_link('https://calendar.google.com', 'Calendar')}
    </section>
    <section class='grid'>
      <article class='card'><h2>Bookmarks</h2>{bookmark_html}</article>
      <article class='card'><h2>Recent History</h2>{history_html}</article>
    </section>
  </div>
</body>
</html>
"""


class PythonBrowserQtApp:
    @staticmethod
    def run_app():
        app = QtWidgets.QApplication([])
        app.setStyle("Fusion")
        win = PythonBrowserQtWindow()
        app.aboutToQuit.connect(win._save_session)
        icon_path = os.path.join(os.path.dirname(__file__), "org.evans.PythonBrowser.svg")
        if os.path.exists(icon_path):
            win.setWindowIcon(QtGui.QIcon(icon_path))
        win.show()
        app.exec()
