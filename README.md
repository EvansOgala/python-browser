# Python Browser (GTK4 + WebKit)

Local-first GTK4 browser with profiles, persistent sign-ins, and session restore.

## Features

- Rounded GTK4 UI with Material-style theming
- Multi-tab browsing
- Back/forward/reload/stop/home controls
- URL + search bar
- Keyboard shortcuts: `Ctrl+L`, `Ctrl+T`, `Ctrl+W`, `Ctrl+R`, `Ctrl+H`
- Multiple profiles with isolated local data
- Persistent cookies/sign-ins per profile
- Local history, bookmarks, and tab session restore
- Download handling to `~/Downloads`

## Data location

All browser data is local only under:

- `~/.local/share/python-browser`

Per profile:

- `profiles/<profile-slug>/webkit-data`
- `profiles/<profile-slug>/webkit-cache`
- `profiles/<profile-slug>/cookies.sqlite`
- `profiles/<profile-slug>/history.db`
- `profiles/<profile-slug>/bookmarks.json`
- `profiles/<profile-slug>/session.json`

## Dependencies

### Runtime

- Python 3.11+
- GTK4 + PyGObject
- WebKitGTK for GTK4 (`WebKit 6.0` GI namespace)
- libsoup3

### Install dependencies by distro

#### Arch Linux / Nyarch

```bash
sudo pacman -S --needed python python-gobject gtk4 webkitgtk-6.0 libsoup3
```

#### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0 libsoup-3.0-0
```

#### Fedora

```bash
sudo dnf install -y python3 python3-gobject gtk4 webkitgtk6.0 libsoup3
```

## Run from source

```bash
cd /home/'your username'/Documents/python-browser
python3 main.py
```

Optional debug mode (enables devtools + JS console logs):

```bash
PYTHON_BROWSER_DEBUG=1 python3 main.py
```

## Build AppImage

### Build requirements

```bash
python3 -m pip install --user pyinstaller
```

Install `appimagetool` in `PATH`, or place one of these files in `./tools/`:

- `appimagetool.AppImage`
- `appimagetool-x86_64.AppImage`

### Build command

```bash
cd /home/'your username'/Documents/python-browser
chmod +x build-appimage.sh
./build-appimage.sh
```

The script outputs an `.AppImage` file in the project root.
