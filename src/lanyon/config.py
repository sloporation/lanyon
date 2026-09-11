"""Loads _config.yml into a dict exposed to templates as `site`."""
from pathlib import Path
import yaml

CONFIG_FILE_NAME = "_config.yml"


def load_site_config(src_root: Path) -> dict:
    config_path = src_root / CONFIG_FILE_NAME
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{CONFIG_FILE_NAME} must contain a YAML mapping at the top level")
    return data
