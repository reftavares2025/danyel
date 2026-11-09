"""Comenta nos posts de quem PROCURA casa, pelo Facebook do Daniel (Chrome separado),
com o WhatsApp dele para contato direto. Pedido do Daniel/Régis em 04/11/2026.

Travas: só posts de compra analisados pela IA (nada de aluguel, vendedor, corretor
anunciando), no máximo `limite_comentarios_dia` por dia, pausa humana entre um
comentário e outro, nunca comenta duas vezes no mesmo post.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from . import navegador

WA_DANIEL = "(19) 90000-0001"

ACHAR_POST_JS = r"""
((trecho) => {
  const norm = t => (t||'').toLowerCase().replace(/[^a-z0-9à-ÿ]+/g,' ').trim();
  const alvo = norm(trecho).slice(0, 60);
  const arts = [...document.querySelectorAll('div[aria-posinset], div[role=article]')];
  const el = arts.find(a => norm(a.innerText).includes(alvo));
  if (!el) return null;
  el.setAttribute('data-dy-alvo', '1');
  const links = [...el.querySelectorAll('a[href]')].filter(a => { const h=a.getAttribute('href')||''; return /^[?#]/.test(h) || h.includes('/search/posts/') || /\/posts\/|\/permalink\/|multi_permalinks=|story_fbid=/.test(a.href); });
  links.forEach((a,i) => a.setAttribute('data-dy-l', i));
  return links.length;
})
"""

LINK_REAL_JS = r"""
(() => {
  const el = document.querySelector('[data-dy-alvo]'); if (!el) return '';
  const h = [...el.querySelectorAll('a[href]')].map(a=>a.href).filter(h=>!/\/search\//.test(h))
    .find(h=>/\/posts\/|\/permalink\/|multi_permalinks=|story_fbid=|\/permalink\.php/.test(h));
  if (!h) return '';
  const u = new URL(h); const g = u.pathname.match(/\/groups\/([^/]+)/), mp = u.searchParams.get('multi_permalinks');
  if (g && mp) return 'https://www.facebook.com/groups/'+g[1]+'/permalink/'+mp.split(',')[0]+'/';
  [...u.searchParams.keys()].filter(k=>k.startsWith('__')).forEach(k=>u.searchParams.delete(k));
  return u.toString();
})()
"""


def eh_link_de_post(url: str) -> bool:
    """Só link direto de um post (nunca busca, feed ou grupo inteiro)."""
    return bool(url) and "/search/" not in url and bool(
        re.search(r"/posts/|/permalink/|story_fbid=|/permalink\.php|multi_permalinks=", url))


def texto_comentario(lead: dict) -> str:
    t = (lead.get("texto") or "").lower()
    a = json.loads(lead.get("analise") or "{}")
    base = ("2 casas completas no mesmo terreno de 440 m² no Jardim Bela Vista III, em Cosmópolis, perto do Centro: "
            "na frente, 3 dormitórios; nos fundos, 2 dormitórios com suíte. Água e luz separadas. R$ 669 mil, "
            "à vista ou com troca + volta em dinheiro.")
    if "chácara" in t or "chacara" in t or "trocar" in t or "troca" in t:
        abertura = "Olá! Aceito troca: tenho para vender, direto com o proprietário,"
        fecho = "Aceito chácara, terreno, carro ou imóvel de menor valor, com volta."
    elif a.get("intencao") == "corretor" or "cliente" in t:
        abertura = "Olá! Para o seu cliente: tenho, direto com o proprietário,"
        fecho = "Aceito terreno, chácara, carro ou imóvel de menor valor na troca."
    else:
        abertura = "Olá! Tenho para vender, direto com o proprietário,"
        fecho = "Aceito terreno, chácara, carro ou imóvel de menor valor na troca."
    return f"{abertura} {base} {fecho} Fale direto comigo no WhatsApp: {WA_DANIEL} – Daniel."


def comentar(cfg: dict, lead: dict, simular: bool = False) -> dict:
    """Abre o post do lead no Facebook do Daniel, comenta e devolve o link do comentário."""
    texto = texto_comentario(lead)
    palavras = re.sub(r"[^\w\sà-ÿ]", " ", lead.get("texto") or "").split()
    busca = "https://www.facebook.com/search/posts/?q=" + quote(" ".join(palavras[:9]))
    post = lead.get("post") or ""
    if not eh_link_de_post(post):
        post = ""  # link de busca NÃO serve: comentaria no primeiro post da lista (erro de 04/11)
    script = navegador.PRELUDIO + f"""
TEXTO = {repr(texto)}
TRECHO = {repr(" ".join(palavras[:14]))}
POST = {repr(post)}
SIMULAR = {simular!r}
ACHAR = {json.dumps(ACHAR_POST_JS)}
LREAL = {json.dumps(LINK_REAL_JS)}
try:
    cdp("Emulation.setFocusEmulationEnabled", enabled=True)
except Exception:
    pass
def mover(sel):
    pos = js("(() => {{ const a=document.querySelector(%s); if(!a) return null; a.scrollIntoView({{block:'center'}}); const r=a.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; }})()" % json.dumps(sel))
    if pos:
        time.sleep(0.3); cdp("Input.dispatchMouseEvent", type="mouseMoved", x=pos[0], y=pos[1]); time.sleep(0.6)
    return pos
res = {{"ok": False, "post": POST, "comentario": "", "motivo": ""}}
if not POST:
    _aba("https://www.facebook.com", {repr(busca)})
    wait_for_load(); time.sleep(random.uniform(5, 7))
    n = js("(" + ACHAR + ")(" + json.dumps(TRECHO) + ")")
    if not n:
        res["motivo"] = "post não encontrado na busca"
    else:
        for i in range(int(n)):
            mover('[data-dy-alvo] a[data-dy-l="%d"]' % i)
        POST = js(LREAL) or ""
        res["post"] = POST
        if not POST:
            res["motivo"] = "não consegui o link do post"
if POST and not res["motivo"] and "/search/" in POST:
    res["motivo"] = "link é de busca, não do post: não comento"
if POST and not res["motivo"]:
    goto_url(POST); wait_for_load(); time.sleep(random.uniform(5, 8))
    # trava: a página aberta tem que ser o post do comprador (texto confere) e não uma lista
    norm = "(t => (t||'').toLowerCase().replace(/[^a-z0-9à-ÿ]+/g,' ').trim())"
    confere = js("(() => {{ const n=%s; const alvo=n(%s).slice(0,50); return !location.pathname.startsWith('/search') && n(document.body.innerText).includes(alvo); }})()" % (norm, json.dumps(TRECHO)))
    if not confere:
        res["motivo"] = "o post aberto não confere com o do comprador: não comentei"
if POST and not res["motivo"]:
    # caixa de comentário (Lexical): clica nela de verdade e digita
    caixa = 'div[role=textbox][contenteditable=true][aria-label*="oment"], div[role=textbox][contenteditable=true][aria-label*="omment"]'
    pos = mover(caixa)
    if not pos:
        js("(() => {{ const b=[...document.querySelectorAll('div[role=button], span')].find(e=>/^(Comentar|Comment)$/.test((e.innerText||'').trim())); if(b) b.click(); }})()")
        time.sleep(2); pos = mover(caixa)
    if not pos:
        res["motivo"] = "caixa de comentário não apareceu (grupo pode exigir participação)"
    elif SIMULAR:
        res.update(ok=True, motivo="simulação: não comentei")
    else:
        for tipo in ("mousePressed", "mouseReleased"):
            cdp("Input.dispatchMouseEvent", type=tipo, x=pos[0], y=pos[1], button="left", clickCount=1)
        time.sleep(1)
        cdp("Input.insertText", text=TEXTO); time.sleep(random.uniform(1.5, 2.5))
        digitado = js("((document.activeElement||{{}}).innerText||'')")
        if TEXTO[:40] not in (digitado or "").replace("\\n", " "):
            res["motivo"] = "texto não entrou na caixa"
        else:
            for tipo in ("keyDown", "keyUp"):
                cdp("Input.dispatchKeyEvent", type=tipo, key="Enter", code="Enter", windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)
            time.sleep(random.uniform(5, 7))
            # confere: o comentário apareceu publicado e pega o link dele
            achou = js("(() => {{ const t=%s; const c=[...document.querySelectorAll('div[role=article][aria-label]')].find(a=>(a.innerText||'').includes(t)); if(!c) return null; c.setAttribute('data-dy-c','1'); [...c.querySelectorAll('a[href]')].forEach((a,i)=>a.setAttribute('data-dy-cl', i)); return c.querySelectorAll('a[href]').length; }})()" % json.dumps(TEXTO[:50]))
            if not achou:
                ainda = js("((document.querySelector(%s)||{{}}).innerText||'')" % json.dumps(caixa))
                res["motivo"] = "comentário não apareceu" + (" (ficou na caixa)" if TEXTO[:30] in (ainda or "") else "")
            else:
                for i in range(int(achou)):
                    mover('[data-dy-c] a[data-dy-cl="%d"]' % i)
                link = js("(() => {{ const c=document.querySelector('[data-dy-c]'); const h=[...c.querySelectorAll('a[href]')].map(a=>a.href).find(h=>h.includes('comment_id')); if(!h) return ''; const u=new URL(h); [...u.searchParams.keys()].filter(k=>k.startsWith('__')).forEach(k=>u.searchParams.delete(k)); return u.toString(); }})()") or ""
                res.update(ok=True, comentario=link or POST)
_fim(res)
"""
    r = navegador.rodar(script, cfg, timeout=240, perfil="facebook")
    r["texto"] = texto
    return r


def localizar_posts(cfg: dict, leads: list[dict], buscas: list[str]) -> dict:
    """Refaz as buscas, acha cada post pelo texto e pega o link verdadeiro (passando o mouse).
    Retorna {lead_id: link}."""
    alvos = {}
    for l in leads:
        p = re.sub(r"[^\w\sà-ÿ]", " ", l.get("texto") or "").split()
        alvos[str(l["id"])] = " ".join(p[:14])
    script = navegador.PRELUDIO + f"""
ALVOS = {json.dumps(alvos, ensure_ascii=True)}
BUSCAS = {repr(list(buscas))}
ACHAR = {json.dumps(ACHAR_POST_JS)}
LREAL = {json.dumps(LINK_REAL_JS)}
from urllib.parse import quote
try:
    cdp("Emulation.setFocusEmulationEnabled", enabled=True)
except Exception:
    pass
def mover(sel):
    pos = js("(() => {{ const a=document.querySelector(%s); if(!a) return null; a.scrollIntoView({{block:'center'}}); const r=a.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; }})()" % json.dumps(sel))
    if pos:
        time.sleep(0.25); cdp("Input.dispatchMouseEvent", type="mouseMoved", x=pos[0], y=pos[1]); time.sleep(0.5)
achados = {{}}
for i, q in enumerate(BUSCAS):
    faltam = [k for k in ALVOS if k not in achados]
    if not faltam:
        break
    url = "https://www.facebook.com/search/posts/?q=" + quote(q)
    if i == 0:
        _aba("https://www.facebook.com", url)
    else:
        goto_url(url)
    wait_for_load(); time.sleep(random.uniform(4, 6))
    for _ in range(3):
        js("window.scrollBy(0, 1800 + Math.random()*900)"); time.sleep(random.uniform(2, 3))
    for k in faltam:
        js("document.querySelectorAll('[data-dy-alvo]').forEach(e=>e.removeAttribute('data-dy-alvo'))")
        n = js("(" + ACHAR + ")(" + json.dumps(ALVOS[k]) + ")")
        if not n:
            continue
        for j in range(int(n)):
            mover('[data-dy-alvo] a[data-dy-l="%d"]' % j)
        link = js(LREAL)
        if link:
            achados[k] = link
    time.sleep(random.uniform(4, 8))
_fim(achados)
"""
    return {int(k): v for k, v in navegador.rodar(script, cfg, timeout=900, perfil="facebook").items()}
