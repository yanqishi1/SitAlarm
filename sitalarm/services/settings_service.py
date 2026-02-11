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
