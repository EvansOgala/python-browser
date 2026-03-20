import os


def _run_linux_gtk():
    from ui import PythonBrowserApp

    app = PythonBrowserApp()
    app.run(None)


def _run_qt():
    from pyside_ui import PythonBrowserQtApp

    PythonBrowserQtApp.run_app()


def _run_windows_webview2():
    from win_webview2_ui import PythonBrowserWebView2App

    PythonBrowserWebView2App.run_app()


def _get_windows_engine() -> str:
    env_engine = os.environ.get("PYTHON_BROWSER_ENGINE", "").strip().lower()
    if env_engine in {"pyside", "webview2"}:
        return env_engine
    try:
        from storage import BrowserStorage

        return BrowserStorage().preferred_engine()
    except Exception:
        return "pyside"


def main():
    if os.name == "nt":
        engine = _get_windows_engine()
        try:
            if engine == "webview2":
                _run_windows_webview2()
            else:
                _run_qt()
            return
        except Exception as exc:
            print("Windows launch failed.")
            print(exc)
            print("Install dependencies:")
            print("py -m pip install PySide6 PySide6-Addons")
            print("py -m pip install pywebview")
            print("winget install Microsoft.EdgeWebView2Runtime")
            raise SystemExit(1)

    try:
        _run_linux_gtk()
    except Exception as gtk_exc:
        try:
            _run_qt()
        except Exception as qt_exc:
            print("GTK launch failed:")
            print(gtk_exc)
            print("Qt fallback launch failed:")
            print(qt_exc)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
