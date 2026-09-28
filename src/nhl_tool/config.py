"""Configuration loading. Single YAML file, paths resolved against repo root."""
import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | os.PathLike | None = None) -> dict:
    cfg_path = Path(
        path
        or os.environ.get("NHL_TOOL_CONFIG")
        or PROJECT_ROOT / "config" / "config.yaml"
    )
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("_root", str(PROJECT_ROOT))
    return cfg


def _resolve(cfg: dict, p: str | os.PathLike) -> Path:
    p = Path(p)
    return p if p.is_absolute() else Path(cfg["_root"]) / p


def resolve_db_path(cfg: dict) -> Path:
    return _resolve(cfg, cfg["database"]["path"])


def resolve_cache_dir(cfg: dict) -> Path:
    return _resolve(cfg, cfg["raw_cache_dir"])


def enabled_season_types(cfg: dict) -> list[str]:
    return [k for k, v in cfg["season_types"].items() if v]
