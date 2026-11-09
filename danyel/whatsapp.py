"""Envio e leitura pelo WhatsApp Web que já está logado no seu Chrome."""
from __future__ import annotations

import json
import re

from . import navegador


def _so_digitos(n: str) -> str:
    return re.sub(r"\D", "", n or "")


_QUEBRADO = re.compile(r"Ã[\u0080-¿£¡¢§©ª«³µº¼½¾]|â€|ðŸ|Â[ -¿]|�|[\ud800-\udfff]")


def texto_integro(texto: str) -> bool:
    """False se o texto tem acentuação quebrada (ex.: 'vocÃª', 'ðŸ¤–', '�')."""
    return not _QUEBRADO.search(texto or "")


def _comparavel(t: str) -> str:
    """Só letras e números: o WhatsApp tira *negrito*, troca emoji por imagem e
    quebra listas em blocos, então comparar pontuação gera alarme falso."""
    t = re.sub(r"[0-9#*]️?⃣", "", t or "")  # emojis 1️⃣ 2️⃣ viram imagem
    return re.sub(r"[^0-9a-zà-ÿ]+", "", t.lower())


# Abre a conversa SEM recarregar o WhatsApp Web (pedido do Régis em 07/11/2026: o robô
# não pode "fechar e abrir de novo" o WhatsApp dele a cada envio).
# 1) clica num link wa.me criado na própria página: o WhatsApp Web abre a conversa por dentro;
# 2) se não der, abre a página oficial com o número completo (recarrega, mas é seguro);
# nunca procura por pedaço do número (risco de abrir a conversa de outra pessoa).
ABRIR_CONVERSA = r'''
def _cabecalho():
    return js("((document.querySelector('#main header span[dir=\"auto\"]')||{}).innerText||'')") or ""
def _caixa():
    return bool(js("!!document.querySelector('footer div[contenteditable=\"true\"]')"))
def _esperar_troca(antes, seg=8):
    for _ in range(seg * 2):
        time.sleep(0.5)
        if _caixa() and _cabecalho() and _cabecalho() != antes:
            return True
    return False
def _abrir_conversa(numero):
    alvo = None
    for t in list_tabs():
        if t["url"].startswith("https://web.whatsapp.com"):
            alvo = t; break
    if not alvo:
        new_tab("https://web.whatsapp.com/send?phone=" + numero)
        return "nova_aba"
    switch_tab(alvo["targetId"])
    # fecha a conversa aberta (Esc), assim qualquer conversa que abrir é a do número pedido
    if js("!!document.querySelector('#main')"):
        cdp("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        cdp("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        time.sleep(1)
    antes = _cabecalho() if js("!!document.querySelector('#main')") else ""
    js("""(() => { const a = document.createElement('a'); a.href = 'https://wa.me/%s'; a.textContent = '.';
        a.style.cssText = 'position:fixed;left:-9999px;top:0'; (document.querySelector('#app')||document.body).appendChild(a);
        a.click(); setTimeout(() => a.remove(), 3000); })()""" % numero)
    if _esperar_troca(antes):
        return "link"
    # Sem busca por pedaço do número: poderia abrir a conversa errada e mandar dados do lead
    # para outra pessoa. Se o link interno não abriu, usa a página oficial com o número completo.
    goto_url("https://web.whatsapp.com/send?phone=" + numero)
    return "recarregou"
def _colar(texto):
    """Cola o texto na caixa da conversa (quebras de linha preservadas, sem apertar Enter)."""
    return js("""((t) => { const b = document.querySelector('footer div[contenteditable="true"]'); if (!b) return false; b.focus();
        const dt = new DataTransfer(); dt.setData('text/plain', t);
        b.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
        return true; })(%s)""" % json.dumps(texto))
'''


def enviar(cfg: dict, numero: str, texto: str) -> bool:
    numero = _so_digitos(numero)
    texto = texto.replace("\r\n", "\n").strip()
    if not texto_integro(texto):
        raise RuntimeError("texto com acentuação quebrada: envio bloqueado")
    script = navegador.PRELUDIO + ABRIR_CONVERSA + f"""
como = _abrir_conversa({numero!r})
colado = False
ok = False; motivo = "caixa de mensagem não apareceu"
for _ in range(45):
    if not colado and _caixa():
        time.sleep(1); _colar({texto!r}); colado = True
    time.sleep(1)
    estado = js('''(() => {{
      const inv = [...document.querySelectorAll('div[role="dialog"], div[data-animate-modal-popup]')].map(d=>d.innerText).join(' ');
      if (/inválido|invalid|não está no WhatsApp|isn.t on WhatsApp/i.test(inv)) return 'invalido';
      const box = document.querySelector('footer div[contenteditable="true"]');
      return box && box.innerText.trim().length > 0 ? 'pronto' : 'esperando';
    }})()''')
    if estado == 'invalido':
        motivo = "número não tem WhatsApp"; break
    if estado == 'pronto':
        conversa = js("((document.querySelector('#main header span[dir=\\"auto\\"]')||{{}}).innerText||'')")
        time.sleep(random.uniform(1.5, 3))
        js('''(() => {{
          const b = document.querySelector('button[aria-label="Enviar"], button[aria-label="Send"], span[data-icon="send"], span[data-icon="wds-ic-send-filled"]');
          (b && (b.closest('button') || b)).click();
        }})()''')
        time.sleep(4)
        vazio = js('''(() => {{ const b=document.querySelector('footer div[contenteditable="true"]'); return !b || b.innerText.trim()==='' }})()''')
        ok = bool(vazio); motivo = "" if ok else "não confirmou o envio"
        break
ultima = js('''(() => {{ const c=[...document.querySelectorAll('#main [data-pre-plain-text]')]
    .filter(e => !e.parentElement.closest('[data-pre-plain-text]')).pop();
  return c ? c.innerText : '' }})()''') or ''
agora_em = js("((document.querySelector('#main header span[dir=\\"auto\\"]')||{{}}).innerText||'')")
_fim({{"ok": ok, "motivo": motivo, "ultima": ultima, "como": como,
       "mesma_conversa": bool(ok) and agora_em == conversa}})
"""
    r = navegador.rodar(script, cfg, timeout=180)
    if not r.get("ok"):
        raise RuntimeError(f"WhatsApp para {numero}: {r.get('motivo')}")
    if not r.get("mesma_conversa"):
        # alguém trocou de conversa no WhatsApp Web durante o envio: não dá para
        # conferir na tela, mas o envio já foi confirmado pela caixa vazia
        return True
    # conferência: o que apareceu na conversa tem que ser exatamente o que mandamos
    ultima = r.get("ultima") or ""
    if not texto_integro(ultima) or _comparavel(texto)[:80] not in _comparavel(ultima):
        raise RuntimeError("enviado, mas o texto na conversa não confere com o original: "
                           f"{ultima[:60]!r}")
    return True


def ler_recebidas(cfg: dict, numero: str, ultimas: int = 15) -> list[dict]:
    """Últimas mensagens RECEBIDAS na conversa com esse número."""
    numero = _so_digitos(numero)
    script = navegador.PRELUDIO + ABRIR_CONVERSA + f"""
_abrir_conversa({numero!r})
msgs = []
for _ in range(40):
    time.sleep(1)
    if js("!!document.querySelector('footer div[contenteditable=\\\"true\\\"]')"):
        time.sleep(3)
        # recebida = remetente igual ao nome do contato no topo da conversa
        msgs = json.loads(js('''(() => {{
          const contato = ((document.querySelector('#main header span[dir="auto"]') || {{}}).innerText || '').trim();
          if (!contato) return '[]';
          return JSON.stringify([...document.querySelectorAll('#main [data-pre-plain-text]')]
            .filter(c => c.getAttribute('data-pre-plain-text').includes('] ' + contato + ':'))
            .slice(-{ultimas})
            .map(c => ({{quando: c.getAttribute('data-pre-plain-text'),
                        texto: (c.querySelector('span.selectable-text') || c).innerText.trim()}})));
        }})()'''))
        break
_fim(msgs)
"""
    return navegador.rodar(script, cfg, timeout=120)


def previa(cfg: dict, nome_contato: str) -> str:
    """Última linha mostrada na lista de conversas para esse contato, SEM abrir
    a conversa e sem mexer no que você está fazendo no WhatsApp Web."""
    script = navegador.PRELUDIO + f"""
alvo = None
for t in list_tabs():
    if t["url"].startswith("https://web.whatsapp.com"):
        alvo = t; break
if not alvo:
    _fim({{"previa": "", "erro": "WhatsApp Web não está aberto"}})
else:
    switch_tab(alvo["targetId"])
    txt = js('''(() => {{
      const s = [...document.querySelectorAll('#pane-side span[title]')].find(e => e.getAttribute('title') === {repr(nome_contato)});
      if (!s) return '';
      const linha = s.closest('[role="listitem"], [role="row"]') || s.parentElement.parentElement.parentElement;
      return linha ? linha.innerText : '';
    }})()''') or ''
    _fim({{"previa": txt.strip().splitlines()[-1] if txt.strip() else ""}})
"""
    return navegador.rodar(script, cfg, timeout=60).get("previa", "")
