"""Ponte com o SEU Chrome (já logado) através do browser-harness.

O Chrome precisa estar aberto com a depuração remota ligada
(chrome://inspect/#remote-debugging). O harness mantém uma conexão única,
então o Chrome não pede "Permitir" a cada execução.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess

MARCA = "DANYEL_JSON:"


def achar_harness(cfg: dict | None = None) -> str:
    conf = ((cfg or {}).get("navegador") or {}).get("harness", "")
    if conf and os.path.exists(conf):
        return conf
    exe = shutil.which("browser-harness")
    if exe:
        return exe
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "uv", "cache", "archive-v0", "*", "Scripts", "browser-harness.exe")
    achados = sorted(glob.glob(base), key=os.path.getmtime, reverse=True)
    if achados:
        return achados[0]
    raise RuntimeError("browser-harness não encontrado. Configure navegador.harness no danyel.yaml.")


def rodar(script: str, cfg: dict | None = None, timeout: int = 600, perfil: str | None = None):
    """Roda um script Python dentro do harness e devolve o JSON impresso com MARCA.

    perfil="facebook": usa o Chrome separado logado no Facebook do aprovador (Daniel),
    se navegador.facebook_cdp estiver configurado. Sem isso, usa o seu Chrome."""
    # O harness lê a entrada com a codificação do Windows: mandamos o script só
    # em ASCII (acentos viram ã dentro das strings) para nada se quebrar.
    script = script.encode("ascii", "backslashreplace").decode("ascii")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cdp = ((cfg or {}).get("navegador") or {}).get("facebook_cdp", "") if perfil == "facebook" else ""
    if cdp:
        env.update(BU_NAME="daniel", BU_CDP_URL=cdp)
    r = subprocess.run([achar_harness(cfg)], input=script, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=env)
    for linha in reversed((r.stdout or "").splitlines()):
        if linha.startswith(MARCA):
            return json.loads(linha[len(MARCA):])
    raise RuntimeError(f"navegador falhou: {(r.stderr or r.stdout or '')[-600:]}")


PRELUDIO = r'''
import json, time, random
def _aba(prefixo, url):
    for t in list_tabs():
        if t["url"].startswith(prefixo):
            switch_tab(t["targetId"]); goto_url(url); return
    new_tab(url)
def _fim(obj):
    print("DANYEL_JSON:" + json.dumps(obj, ensure_ascii=True))
'''
