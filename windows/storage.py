from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip())
    cleaned = cleaned.strip("-._")
    return cleaned.lower() or "profile"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if not parsed.scheme:
        return f"https://{text}"
    return text


class BrowserStorage:
    def __init__(self, base_dir: Path | None = None):
        env_dir = os.environ.get("PYTHON_BROWSER_DATA_DIR", "").strip()
        if env_dir:
            default_base = Path(env_dir).expanduser()
        elif os.name == "nt":
            localappdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
            default_base = Path(localappdata) / "Python Browser"
        else:
            default_base = Path.home() / ".local" / "share" / "python-browser"
        preferred = base_dir or default_base
        self.base_dir = self._ensure_base_dir(preferred)
        profiles_folder = "Profiles" if os.name == "nt" else "profiles"
        self.profiles_dir = self.base_dir / profiles_folder
        self.config_path = self.base_dir / "config.json"

        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_windows_data()
        self.config = self._load_or_init_config()

    def _ensure_base_dir(self, preferred: Path) -> Path:
        try:
            preferred.mkdir(parents=True, exist_ok=True)
            return preferred
        except PermissionError:
            pass

        fallbacks = [Path.home() / "Documents" / ".python-browser-data"]
        if os.name != "nt":
            fallbacks.append(Path("/tmp") / "python-browser-data")
        for path in fallbacks:
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except PermissionError:
                continue

        # Re-raise with the originally requested location for clarity.
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred

    def _migrate_legacy_windows_data(self) -> None:
        if os.name != "nt":
            return

        try:
            has_profiles = any(self.profiles_dir.iterdir())
        except OSError:
            has_profiles = False
        if self.config_path.exists() or has_profiles:
            return

        appdata = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        localappdata = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        candidates = [
            appdata / "python-browser",
            appdata / "Python Browser",
            localappdata / "python-browser",
            Path.home() / ".local" / "share" / "python-browser",
            Path.home() / "Documents" / ".python-browser-data",
        ]

        for src_base in candidates:
            try:
                if src_base.resolve() == self.base_dir.resolve():
                    continue
            except OSError:
                continue
            if not src_base.exists():
                continue

            src_config = src_base / "config.json"
            if src_config.exists() and not self.config_path.exists():
                try:
                    shutil.copy2(src_config, self.config_path)
                except OSError:
                    pass

            for folder_name in ("profiles", "Profiles"):
                src_profiles = src_base / folder_name
                if not src_profiles.exists():
                    continue
                for child in src_profiles.iterdir():
                    target = self.profiles_dir / child.name
                    try:
                        if child.is_dir():
                            shutil.copytree(child, target, dirs_exist_ok=True)
                        elif child.is_file() and not target.exists():
                            shutil.copy2(child, target)
                    except OSError:
                        continue

    def _default_config(self) -> dict:
        return {
            "current_profile": "Default",
            "preferred_engine": "pyside",
            "profiles": [
                {
                    "name": "Default",
                    "slug": "default",
                    "home_url": "browser://home",
                    "search_url": "https://www.google.com/search?q={query}",
                }
            ],
        }

    def _load_or_init_config(self) -> dict:
        if not self.config_path.exists():
            config = self._default_config()
            self._write_config(config)
            self._ensure_profile_data(config["profiles"][0])
            return config

        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            config = self._default_config()

        profiles = config.get("profiles")
        if not isinstance(profiles, list) or not profiles:
            profiles = self._default_config()["profiles"]

        normalized_profiles = []
        seen = set()
        for item in profiles:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            slug = str(item.get("slug", "")).strip() or _slugify(name)
            search_url = str(item.get("search_url", "https://www.google.com/search?q={query}")).strip()
            if not search_url:
                search_url = "https://www.google.com/search?q={query}"
            if "duckduckgo.com" in search_url.lower():
                search_url = "https://www.google.com/search?q={query}"

            normalized_profiles.append(
                {
                    "name": name,
                    "slug": slug,
                    "home_url": str(item.get("home_url", "browser://home")) or "browser://home",
                    "search_url": search_url,
                }
            )

        if not normalized_profiles:
            normalized_profiles = self._default_config()["profiles"]

        current = str(config.get("current_profile", normalized_profiles[0]["name"]))
        names = {p["name"] for p in normalized_profiles}
        if current not in names:
            current = normalized_profiles[0]["name"]

        out = {
            "current_profile": current,
            "preferred_engine": str(config.get("preferred_engine", "pyside")).strip().lower() or "pyside",
            "profiles": normalized_profiles,
        }
        if out["preferred_engine"] not in {"pyside", "webview2"}:
            out["preferred_engine"] = "pyside"

        self._write_config(out)
        for profile in out["profiles"]:
            self._ensure_profile_data(profile)
        return out

    def _write_config(self, config: dict) -> None:
        self.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    def save(self) -> None:
        self._write_config(self.config)

    def list_profiles(self) -> list[dict]:
        return list(self.config.get("profiles", []))

    def profile_names(self) -> list[str]:
        return [p["name"] for p in self.list_profiles()]

    def get_profile(self, name: str | None = None) -> dict:
        target = name or self.current_profile_name()
        for profile in self.list_profiles():
            if profile["name"] == target:
                return profile
        return self.list_profiles()[0]

    def current_profile_name(self) -> str:
        current = str(self.config.get("current_profile", ""))
        names = self.profile_names()
        if current in names:
            return current
        fallback = names[0]
        self.config["current_profile"] = fallback
        self.save()
        return fallback

    def set_current_profile(self, name: str) -> None:
        if name not in self.profile_names():
            raise ValueError(f"Unknown profile: {name}")
        self.config["current_profile"] = name
        self.save()

    def preferred_engine(self) -> str:
        value = str(self.config.get("preferred_engine", "pyside")).strip().lower()
        if value not in {"pyside", "webview2"}:
            value = "pyside"
        if self.config.get("preferred_engine") != value:
            self.config["preferred_engine"] = value
            self.save()
        return value

    def set_preferred_engine(self, engine: str) -> None:
        value = str(engine).strip().lower()
        if value not in {"pyside", "webview2"}:
            raise ValueError(f"Unsupported engine: {engine}")
        self.config["preferred_engine"] = value
        self.save()

    def add_profile(self, name: str) -> dict:
        profile_name = name.strip()
        if not profile_name:
            raise ValueError("Profile name cannot be empty")

        if profile_name.lower() in {n.lower() for n in self.profile_names()}:
            raise ValueError("Profile already exists")

        slug_base = _slugify(profile_name)
        slug = slug_base
        existing = {p.get("slug", "") for p in self.list_profiles()}
        i = 2
        while slug in existing:
            slug = f"{slug_base}-{i}"
            i += 1

        profile = {
            "name": profile_name,
            "slug": slug,
            "home_url": "browser://home",
            "search_url": "https://www.google.com/search?q={query}",
        }
        self.config.setdefault("profiles", []).append(profile)
        self._ensure_profile_data(profile)
        self.save()
        return profile

    def profile_dir(self, name: str | None = None) -> Path:
        profile = self.get_profile(name)
        return self.profiles_dir / profile["slug"]

    def _ensure_profile_data(self, profile: dict) -> None:
        pdir = self.profiles_dir / profile["slug"]
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "webkit-data").mkdir(parents=True, exist_ok=True)
        (pdir / "webkit-cache").mkdir(parents=True, exist_ok=True)

        bookmarks = pdir / "bookmarks.json"
        if not bookmarks.exists():
            bookmarks.write_text("[]", encoding="utf-8")

        session = pdir / "session.json"
        if not session.exists():
            session.write_text(json.dumps({"tabs": ["browser://home"], "current_index": 0}, indent=2), encoding="utf-8")

        self._ensure_history_db(pdir)

    def _history_path(self, name: str | None = None) -> Path:
        return self.profile_dir(name) / "history.db"

    def _ensure_history_db(self, profile_dir: Path) -> None:
        db = profile_dir / "history.db"
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  url TEXT NOT NULL,
                  title TEXT,
                  last_visited TEXT NOT NULL,
                  visit_count INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_history_url ON history(url)")
            conn.commit()

    def add_history(self, profile_name: str, url: str, title: str) -> None:
        final_url = _normalize_url(url)
        if not final_url or final_url.startswith("browser://"):
            return

        db = self._history_path(profile_name)
        now = _now_iso()
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                INSERT INTO history(url, title, last_visited, visit_count)
                VALUES(?, ?, ?, 1)
                ON CONFLICT(url) DO UPDATE SET
                  title=excluded.title,
                  last_visited=excluded.last_visited,
                  visit_count=history.visit_count + 1
                """,
                (final_url, title[:1024], now),
            )
            conn.commit()

    def recent_history(self, profile_name: str, limit: int = 200) -> list[dict]:
        db = self._history_path(profile_name)
        limit = max(1, min(1000, int(limit)))
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT url, title, last_visited, visit_count FROM history ORDER BY last_visited DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_history(self, profile_name: str) -> None:
        db = self._history_path(profile_name)
        with sqlite3.connect(db) as conn:
            conn.execute("DELETE FROM history")
            conn.commit()

    def bookmarks_path(self, profile_name: str) -> Path:
        return self.profile_dir(profile_name) / "bookmarks.json"

    def list_bookmarks(self, profile_name: str) -> list[dict]:
        path = self.bookmarks_path(profile_name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip() or url
            if not url:
                continue
            out.append(
                {
                    "url": url,
                    "title": title,
                    "added": str(item.get("added", "")) or _now_iso(),
                }
            )
        return out

    def save_bookmarks(self, profile_name: str, bookmarks: list[dict]) -> None:
        path = self.bookmarks_path(profile_name)
        path.write_text(json.dumps(bookmarks, indent=2), encoding="utf-8")

    def add_bookmark(self, profile_name: str, title: str, url: str) -> None:
        final_url = _normalize_url(url)
        if not final_url:
            return
        bookmarks = self.list_bookmarks(profile_name)
        if any(b.get("url") == final_url for b in bookmarks):
            return
        bookmarks.append({"title": title.strip() or final_url, "url": final_url, "added": _now_iso()})
        self.save_bookmarks(profile_name, bookmarks)

    def remove_bookmark(self, profile_name: str, url: str) -> None:
        final_url = _normalize_url(url)
        bookmarks = [b for b in self.list_bookmarks(profile_name) if b.get("url") != final_url]
        self.save_bookmarks(profile_name, bookmarks)

    def session_path(self, profile_name: str) -> Path:
        return self.profile_dir(profile_name) / "session.json"

    def load_session(self, profile_name: str) -> dict:
        path = self.session_path(profile_name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {"tabs": ["browser://home"], "current_index": 0}

        tabs = data.get("tabs")
        if not isinstance(tabs, list) or not tabs:
            tabs = ["browser://home"]
        tabs = [str(t).strip() or "browser://home" for t in tabs]

        idx = data.get("current_index", 0)
        try:
            idx = int(idx)
        except Exception:  # noqa: BLE001
            idx = 0
        idx = max(0, min(len(tabs) - 1, idx))

        return {"tabs": tabs, "current_index": idx}

    def save_session(self, profile_name: str, tabs: list[str], current_index: int) -> None:
        path = self.session_path(profile_name)
        clean_tabs = [str(t).strip() or "browser://home" for t in tabs] or ["browser://home"]
        idx = max(0, min(len(clean_tabs) - 1, int(current_index)))
        payload = {"tabs": clean_tabs, "current_index": idx, "updated": _now_iso()}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
