from __future__ import annotations

from dataclasses import asdict

from sitalarm.config import AppSettings, DEFAULT_SETTINGS
from sitalarm.services.storage import Storage


class SettingsService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def load(self) -> AppSettings:
        data = asdict(DEFAULT_SETTINGS)
        stored = self.storage.all_settings()

        # Backward compatibility: migrate old minutes-based interval to seconds.
        # Older versions used `capture_interval_minutes`.
        if "capture_interval_seconds" in data and "capture_interval_seconds" not in stored:
            legacy_minutes = stored.get("capture_interval_minutes")
            if legacy_minutes is not None:
                try:
                    data["capture_interval_seconds"] = max(1, int(legacy_minutes) * 60)
                except ValueError:
                    pass

        for key, value in stored.items():
            if key not in data:
                continue
            if isinstance(data[key], bool):
                data[key] = value.lower() == "true"
            elif isinstance(data[key], int):
                data[key] = int(value)
            elif isinstance(data[key], float):
                data[key] = float(value)
            else:
                data[key] = value

        # Normalize legacy/Chinese detection-mode aliases.
        data["detection_mode"] = self._normalize_detection_mode(data.get("detection_mode"))
        return AppSettings(**data)

    def update(self, **changes: object) -> AppSettings:
        current = asdict(self.load())
        for key, value in changes.items():
            if key not in current:
                continue
            current[key] = value

        normalized = AppSettings(**current)
        payload = asdict(normalized)
        for key, value in payload.items():
            self.storage.set_setting(key, str(value))
        return normalized

    @staticmethod
    def _normalize_detection_mode(value: object) -> str:
        mode = str(value or "normal").lower().strip()
        if mode in ("strict", "严格"):
            return "strict"
        if mode in ("normal", "正常"):
            return "normal"
        if mode in ("loose", "宽松"):
            return "loose"
        return "normal"

    def get_setting(self, key: str) -> str | None:
        """获取指定 key 的设置值"""
        return self.storage.get_setting(key)

    def set_setting(self, key: str, value: str) -> None:
        """设置指定 key 的设置值"""
        self.storage.set_setting(key, value)
