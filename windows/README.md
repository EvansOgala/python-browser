# Python Browser

Local-first desktop browser with profile-aware storage and session restore.

## Windows Runtime

Windows now supports two engines:

- `pyside` (default): full app UI (tabs, history, bookmarks, profiles)
- `webview2`: compatibility mode using Edge WebView2 with menu-based controls and multi-window sessions

Required on Windows:

```powershell
py -m pip install --upgrade pip
py -m pip install PySide6 PySide6-Addons
py -m pip install pywebview pythonnet pywin32
winget install Microsoft.EdgeWebView2Runtime
```

Important:

- PyInstaller does **not** bundle the Microsoft WebView2 Runtime itself.
- Most modern Windows installs already have it, but if missing, install via `winget` above.

## Data Location

- Windows profiles: `%LOCALAPPDATA%\Python Browser\Profiles`
- Windows config: `%LOCALAPPDATA%\Python Browser\config.json`
- Linux: `~/.local/share/python-browser`

Per profile:

- `profiles/<profile-slug>/webview2-data` (Windows WebView2)
- `profiles/<profile-slug>/webkit-data` (Linux GTK/WebKit)
- `profiles/<profile-slug>/webkit-cache` (Linux GTK/WebKit)
- `profiles/<profile-slug>/history.db`
- `profiles/<profile-slug>/bookmarks.json`
- `profiles/<profile-slug>/session.json`

## Run From Source

### Windows

```powershell
cd C:\Users\your-username\Documents\python-browser
py main.py
```

Optional fallback engine:

```powershell
$env:PYTHON_BROWSER_ENGINE="webview2"
py main.py
```

CMD equivalent:

```bat
set PYTHON_BROWSER_ENGINE=webview2
py main.py
```

You can also switch engine in-app (Windows): `Engine` dropdown -> `Apply Engine`.

In `webview2` mode, use the window menu:

- `Browser -> New Window` (multitasking)
- `Browser -> Open URL / Search`
- `Browser -> Back / Forward / Reload / Home`
- `Browser -> Close Window / Quit`

### Linux

```bash
cd /home/'your username'/Documents/python-browser
python3 main.py
```

## Build Windows EXE (PyInstaller)

### Build requirements

```powershell
py -m pip install --upgrade pip pyinstaller
py -m pip install PySide6 PySide6-Addons
py -m pip install pywebview pythonnet pywin32
winget install Microsoft.EdgeWebView2Runtime
```

### Build command

```powershell
cd C:\Users\your-username\Documents\python-browser
build-windows.bat
```

Output:

- `dist\PythonBrowser\PythonBrowser.exe`

Optional icon:

- Drop `app_icon.ico` in the project root before build.

## Linux Dependencies (GTK4 + WebKit)

### Arch Linux / Nyarch

```bash
sudo pacman -S --needed python python-gobject gtk4 webkitgtk-6.0 libsoup3
```

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0 libsoup-3.0-0
```

### Fedora

```bash
sudo dnf install -y python3 python3-gobject gtk4 webkitgtk6.0 libsoup3
```
