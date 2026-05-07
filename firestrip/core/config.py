from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

CONFIG_PATH = Path.home() / ".config" / "firestrip" / "config.toml"

DEFAULT_CONFIG = """\
[connection]
default_host = ""
default_port = 5555

[behaviour]
auto_backup = true
dry_run_default = true

[ui]
theme = "dark"
"""

_log = logging.getLogger("firestrip.config")


@dataclass
class ConnectionConfig:
    default_host: str = ""
    default_port: int = 5555


@dataclass
class BehaviourConfig:
    auto_backup: bool = True
    dry_run_default: bool = True


@dataclass
class UIConfig:
    theme: str = "dark"


@dataclass
class Config:
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    behaviour: BehaviourConfig = field(default_factory=BehaviourConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def _merge(target: object, data: dict) -> None:
    if not is_dataclass(target):
        return
    for f in fields(target):
        if f.name in data:
            value = data[f.name]
            current = getattr(target, f.name)
            if is_dataclass(current) and isinstance(value, dict):
                _merge(current, value)
            else:
                setattr(target, f.name, value)


def load_config() -> Config:
    cfg = Config()
    if not CONFIG_PATH.exists():
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(DEFAULT_CONFIG)
        except OSError as exc:
            _log.warning("Could not write default config: %s", exc)
        return cfg
    try:
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
        _merge(cfg, data)
    except Exception as exc:
        _log.warning("Could not parse config %s: %s", CONFIG_PATH, exc)
    return cfg


def save_config(config: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(config)
    lines: list[str] = []
    for section, values in data.items():
        lines.append(f"[{section}]")
        for k, v in values.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    CONFIG_PATH.write_text("\n".join(lines))
