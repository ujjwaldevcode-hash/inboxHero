"""Persistent user preferences backed by a small JSON file."""
import json
from pathlib import Path


class PreferenceStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, preferences: dict) -> None:
        self.path.write_text(
            json.dumps(preferences, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def set(self, key: str, value) -> None:
        preferences = self.load()
        preferences[key] = value
        self.save(preferences)

    def get(self, key: str, default=None):
        return self.load().get(key, default)
