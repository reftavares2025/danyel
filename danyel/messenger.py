"""Envio de mensagem privada pelo Messenger, com a sua conta do Facebook.

Só é usado para leads APROVADOS pelo Daniel, dentro do limite diário
(robo.limite_facebook_dia). Mensagem para quem não é amigo cai em
"solicitações de mensagem" da pessoa.
"""
from __future__ import annotations

import json
import re

from . import navegador


def destino(perfil_url: str) -> str | None:
    m = re.search(r"profile\.php\?id=(\d+)", perfil_url or "") or re.search(r"/user/(\d+)", perfil_url or "")
    if m:
        return m.group(1)
    m = re.search(r"facebook\.com/([A-Za-z0-9.]{3,})/?$", perfil_url or "")
    return m.group(1) if m else None


def enviar(cfg: dict, perfil_url: str, texto: str) -> bool:
    alvo = destino(perfil_url)
    if not alvo:
        raise RuntimeError("perfil sem identificador")
    script = navegador.PRELUDIO + f"""
_aba("https://www.facebook.com", "https://www.facebook.com/messages/t/{alvo}")
ok = False; motivo = "caixa de mensagem não apareceu"
for _ in range(30):
    time.sleep(1)
    tem = js('''(() => {{ const b=[...document.querySelectorAll('div[role="textbox"][contenteditable="true"]')].pop(); if(!b) return false; b.focus(); return true; }})()''')
    if tem:
        time.sleep(random.uniform(1, 2))
        cdp("Input.insertText", text={repr(texto)})
        time.sleep(random.uniform(1.5, 3))
        for tipo in ("keyDown", "keyUp"):
            cdp("Input.dispatchKeyEvent", type=tipo, key="Enter", code="Enter", windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)
        time.sleep(4)
        vazio = js('''(() => {{ const b=[...document.querySelectorAll('div[role="textbox"][contenteditable="true"]')].pop(); return !b || b.innerText.trim()==='' }})()''')
        ok = bool(vazio); motivo = "" if ok else "não confirmou o envio"
        break
_fim({{"ok": ok, "motivo": motivo}})
"""
    r = navegador.rodar(script, cfg, timeout=120)
    if not r.get("ok"):
        raise RuntimeError(f"Messenger: {r.get('motivo')}")
    return True
