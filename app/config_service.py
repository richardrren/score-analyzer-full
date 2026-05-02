from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .ai_service import AIConfig

APP_DIR = Path.home() / ".exam_analysis_desktop"
CONFIG_FILE = APP_DIR / "config.json"


def load_config() -> AIConfig:
    if not CONFIG_FILE.exists():
        return AIConfig()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AIConfig(
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", "https://api.openai.com/v1"),
            model=data.get("model", ""),
            timeout=int(data.get("timeout", 120)),
        )
    except Exception:
        return AIConfig()


def save_config(config: AIConfig, remember_key: bool = False) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    if not remember_key:
        payload["api_key"] = ""
    CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
