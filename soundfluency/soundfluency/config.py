"""Carrega config.yaml e mescla com overrides por lição."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None, overrides: dict | None = None) -> dict:
    cfg_path = path or DEFAULT_CONFIG
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    return cfg
