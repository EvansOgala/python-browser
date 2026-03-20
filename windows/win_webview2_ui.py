from __future__ import annotations

import urllib.parse
from pathlib import Path

import webview
from webview.menu import Menu, MenuAction, MenuSeparator

from storage import BrowserStorage


def _normalize_uri(raw: str, storage: BrowserStorage, profile_name: str) -> str:
    value = (raw or "").strip()
    if not value:
        return "https://www.google.com"
    if value.startswith("browser://"):
        profile = storage.get_profile(profile_name)
        home = str(profile.get("home_url", "")).strip()
        return home if home and not home.startswith("browser://") else "https://www.google.com"
    if "://" in value:
        return value
    if " " in value:
        return _search_uri(value, storage, profile_name)
    if value.startswith("localhost") or "." in value:
        return f"https://{value}"
    return _search_uri(value, storage, profile_name)


def _search_uri(query: str, storage: BrowserStorage, profile_name: str) -> str:
    profile = storage.get_profile(profile_name)
    template = str(profile.get("search_url", "https://www.google.com/search?q={query}")).strip()
    if not template:
        template = "https://www.google.com/search?q={query}"
    return template.replace("{query}", urllib.parse.quote_plus(query))


class _WebView2Shell:
    def __init__(self):
        self.storage = BrowserStorage()
        self.profile_name = self.storage.current_profile_name()
        self.profile_dir = self.storage.profile_dir(self.profile_name)
        self.storage_dir = self.profile_dir / "webview2-data"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.windows: list[webview.Window] = []

    def _active_window(self) -> webview.Window | None:
        try:
            return webview.active_window()
        except Exception:
            return None

    def _window_title(self) -> str:
        return f"Python Browser - {self.profile_name} [WebView2]"

    def _prompt_and_open(self):
        win = self._active_window()
        if win is None:
            return
        current = ""
        try:
            current = win.get_current_url() or ""
        except Exception:
            current = ""
        script = (
            "window.prompt('Enter URL or search query:', "
            + repr(current if current else "https://www.google.com")
            + ");"
        )
        try:
            entered = win.evaluate_js(script)
        except Exception:
            entered = None
        if not isinstance(entered, str) or not entered.strip():
            return
        win.load_url(_normalize_uri(entered, self.storage, self.profile_name))
        self._save_session()

    def _go_home(self):
        win = self._active_window()
        if win is None:
            return
        win.load_url(_normalize_uri("browser://home", self.storage, self.profile_name))
        self._save_session()

    def _reload(self):
        win = self._active_window()
        if win is None:
            return
        win.run_js("window.location.reload();")

    def _back(self):
        win = self._active_window()
        if win is None:
            return
        win.run_js("window.history.back();")

    def _forward(self):
        win = self._active_window()
        if win is None:
            return
        win.run_js("window.history.forward();")

    def _new_window(self):
        start_url = _normalize_uri("browser://home", self.storage, self.profile_name)
        window = webview.create_window(self._window_title(), start_url, width=1300, height=860)
        self._attach_window_events(window)
        self.windows.append(window)
        self._save_session()

    def _close_window(self):
        win = self._active_window()
        if win is None:
            return
        try:
            win.destroy()
        except Exception:
            return
        self._save_session()

    def _quit_app(self):
        self._save_session()
        for win in list(self.windows):
            try:
                win.destroy()
            except Exception:
                continue

    def _attach_window_events(self, window: webview.Window):
        def _on_closing():
            self._save_session()

        try:
            window.events.closing += _on_closing
        except Exception:
            pass

    def _current_urls(self) -> list[str]:
        urls: list[str] = []
        for win in self.windows:
            try:
                current = win.get_current_url()
            except Exception:
                current = None
            if isinstance(current, str) and current.strip():
                urls.append(current.strip())
        return urls or [_normalize_uri("browser://home", self.storage, self.profile_name)]

    def _save_session(self):
        urls = self._current_urls()
        self.storage.save_session(self.profile_name, urls, 0)

    def _build_menus(self):
        return [
            Menu(
                "Browser",
                [
                    MenuAction("New Window", self._new_window),
                    MenuAction("Open URL / Search", self._prompt_and_open),
                    MenuSeparator(),
                    MenuAction("Back", self._back),
                    MenuAction("Forward", self._forward),
                    MenuAction("Reload", self._reload),
                    MenuAction("Home", self._go_home),
                    MenuSeparator(),
                    MenuAction("Close Window", self._close_window),
                    MenuAction("Quit", self._quit_app),
                ],
            )
        ]

    def run(self):
        session = self.storage.load_session(self.profile_name)
        tabs = session.get("tabs", ["browser://home"]) or ["browser://home"]
        index = int(session.get("current_index", 0))
        if index < 0 or index >= len(tabs):
            index = 0

        first_url = _normalize_uri(tabs[index], self.storage, self.profile_name)
        first = webview.create_window(self._window_title(), first_url, width=1420, height=920)
        self._attach_window_events(first)
        self.windows.append(first)

        for i, uri in enumerate(tabs):
            if i == index:
                continue
            w = webview.create_window(self._window_title(), _normalize_uri(uri, self.storage, self.profile_name), width=1300, height=860)
            self._attach_window_events(w)
            self.windows.append(w)

        webview.start(
            gui="edgechromium",
            private_mode=False,
            storage_path=str(self.storage_dir),
            menu=self._build_menus(),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )


class PythonBrowserWebView2App:
    @staticmethod
    def run_app() -> None:
        shell = _WebView2Shell()
        shell.run()
