from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStorage:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)

    def save(self, data: dict[str, Any]) -> None:
        if self.file_path.parent and not self.file_path.parent.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

        with self.file_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def load(self) -> dict[str, Any] | None:
        if not self.file_path.exists():
            return None

        with self.file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
