from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("LLAMADECK_CONFIG_DIR", Path.home() / ".config" / "llamadeck"))
CONFIG_FILE = CONFIG_DIR / "config.json"
DB_PATH = CONFIG_DIR / "instances.db"

DEFAULT_PORT = 11435
DEFAULT_GGUF_DIR = str(Path.home() / "GGUF-Models")
DEFAULT_HOST = "0.0.0.0"


class Settings:
    def __init__(self) -> None:
        self.port: int = DEFAULT_PORT
        self.host: str = DEFAULT_HOST
        self.gguf_dir: str = DEFAULT_GGUF_DIR

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        if CONFIG_FILE.exists():
            self._load(CONFIG_FILE)

    def _load(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text())
            self.port = data.get("port", self.port)
            self.host = data.get("host", self.host)
            self.gguf_dir = data.get("gguf_dir", self.gguf_dir)
        except (json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        data = {
            "port": self.port,
            "host": self.host,
            "gguf_dir": self.gguf_dir,
        }
        CONFIG_FILE.write_text(json.dumps(data, indent=2))


settings = Settings()
