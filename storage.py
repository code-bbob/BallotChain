from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


class JsonStorage:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)

    def save(self, data: dict[str, Any]) -> None:
        path = self.file_path
        # Docker bind mount may have created a directory for a missing file
        if path.is_dir():
            shutil.rmtree(path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def load(self) -> dict[str, Any] | None:
        if not self.file_path.is_file():
            return None

        with self.file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
