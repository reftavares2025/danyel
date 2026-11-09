"""Leitura do danyel.yaml (e de um danyel.local.yaml opcional por cima)."""
from __future__ import annotations

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data"


def _mesclar(base: dict, extra: dict) -> dict:
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mesclar(base[k], v)
        else:
            base[k] = v
    return base


def carregar(caminho: Path | None = None) -> dict:
    caminho = caminho or RAIZ / "danyel.yaml"
    cfg = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    local = caminho.with_name("danyel.local.yaml")
    if local.exists():
        _mesclar(cfg, yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    cfg.setdefault("ofertas", [])
    cfg.setdefault("caca", {})
    cfg.setdefault("cerebro", {"ligado": True, "modelo": "", "timeout_seg": 120})
    cfg.setdefault("painel", {"porta": 5556, "dias_para_retorno": 2})
    cfg.setdefault("vendedor", {})
    return cfg


def oferta(cfg: dict, oferta_id: str | None) -> dict:
    for o in cfg["ofertas"]:
        if o.get("id") == oferta_id:
            return o
    return cfg["ofertas"][0] if cfg["ofertas"] else {}
