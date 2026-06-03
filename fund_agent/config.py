from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv


@dataclass
class Settings:
    raw: Dict[str, Any]
    config_path: Path

    @property
    def funds(self) -> List[Dict[str, Any]]:
        return self.raw.get("funds", [])

    @property
    def indices(self) -> List[Dict[str, Any]]:
        return self.raw.get("indices", [])

    @property
    def runtime(self) -> Dict[str, Any]:
        return self.raw.get("runtime", {})

    @property
    def output_dir(self) -> Path:
        return Path(self.runtime.get("output_dir", "reports"))

    @property
    def data_dir(self) -> Path:
        return Path(self.runtime.get("data_dir", "data"))

    def env(self, key: str, default: str | None = None) -> str | None:
        value = os.getenv(key)
        return value if value not in (None, "") else default


def load_settings(config_path: str | Path) -> Settings:
    load_dotenv()
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Settings(raw=raw, config_path=path)
