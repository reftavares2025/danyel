"""Varredura da internet pelo Google, com a conta Google do Régis (Chrome dele, já logado).

O Google acha posts de compra no Facebook, Instagram, OLX e sites de imóveis da região
e já devolve o link DIRETO do post (o Facebook, na busca dele, esconde esse link).
Os posts do Facebook são abertos depois no Facebook do Daniel para ler o texto inteiro
e o autor, e só então passam pelos mesmos filtros (compra sim; aluguel e vendedor não).
Só leitura: nada é postado aqui.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from . import navegador

EXTRATOR_JS = r"""
(() => [...document.querySelectorAll('#search a h3')].map(h => {
  const a = h.closest('a'); const c = a.closest('.MjjYud') || a.parentElement;
  const sn = [...c.querySelectorAll('div[data-sncf], .VwiC3b, span')].map(e => e.innerText)
    .sort((x, y) => y.length - x.length)[0] || '';
  return {titulo: h.innerText, url: a.href, trecho: sn.slice(0, 600)};
}))()
"""

LER_POST_JS = r"""
(() => {
  for (const b of document.querySelectorAll('div[role="button"]')) {
    if ((b.innerText||'').trim() === 'Ver mais') { try { b.click(); } catch(e){} }
  }
  const el = document.querySelector('div[role=main] div[aria-posinset], div[role=main] div[role=article], div[role=article]');
  if (!el) return null;
  const msgs = [...el.querySelectorAll('[data-ad-rendering-role="story_message"], [data-ad-preview="message"], div[dir="auto"]')]
    .map(d => d.innerText.trim()).filter(t => t.length > 10);
  const texto = [...new Set(msgs)].sort((a, b) => b.length - a.length)[0] || '';
  const p = [...el.querySelectorAll('a[href*="facebook.com/"]')].find(a => /profile\.php\?id=|\/groups\/[^/]+\/user\/\d+|facebook\.com\/(?!groups|search|photo|watch|hashtag)[A-Za-z0-9.]{3,}(\/|\?|$)/.test(a.href) && (a.innerText||'').trim().length > 1);
  const grupo = ((document.querySelector('h1') || {}).innerText || '').split('\n')[0];
  return {texto: texto.slice(0, 3000), autor: p ? (p.innerText||'').trim().split('\n')[0] : '', perfil: p ? p.href.split('?')[0] : '', grupo: grupo.slice(0, 90)};
})()
"""

REGIAO = ('(Cosmópolis OR "Artur Nogueira" OR Paulínia OR "Engenheiro Coelho" OR Holambra OR '
          'Jaguariúna OR "Santo Antônio de Posse" OR Americana OR Sumaré)')


def montar_buscas(cfg: dict) -> list[str]:
    g = (cfg.get("google") or {})
    if g.get("buscas"):
        return list(g["buscas"])
    return [
        f'"procuro casa para comprar" {REGIAO}',
        f'"quero comprar uma casa" {REGIAO}',
        f'"compro casa" {REGIAO}',
        f'("à vista" OR "permuta" OR "aceito troca") "procuro casa" {REGIAO}',
        f'"procuro casa" comprar site:instagram.com {REGIAO}',
        f'"alguém vendendo casa" {REGIAO}',
    ]


def eh_permalink_facebook(url: str) -> bool:
    return bool(re.search(r"facebook\.com/.+(/posts/\d|/permalink/\d|story_fbid=|multi_permalinks=)", url or ""))


def buscar(cfg: dict, buscas: list[str] | None = None, periodo: str = "qdr:m") -> list[dict]:
    """Roda as buscas no Google (Chrome do Régis) e devolve [{titulo, url, trecho, busca}]."""
    buscas = buscas or montar_buscas(cfg)
    script = navegador.PRELUDIO + f"""
from urllib.parse import quote
EXTR = {json.dumps(EXTRATOR_JS)}
res, vistos = [], set()
for i, q in enumerate({repr(list(buscas))}):
    url = "https://www.google.com/search?hl=pt-BR&num=30&tbs={periodo}&q=" + quote(q)
    if i == 0:
        _aba("https://www.google.com/search", url)
    else:
        goto_url(url)
    wait_for_load(); time.sleep(random.uniform(3, 5))
    if "/sorry" in js("location.href"):
        break  # o Google pediu captcha: para por hoje
    for r in js(EXTR) or []:
        if r["url"] in vistos:
            continue
        vistos.add(r["url"]); r["busca"] = q; res.append(r)
    time.sleep(random.uniform(5, 9))
_fim(res)
"""
    return navegador.rodar(script, cfg, timeout=600)


def ler_posts_facebook(cfg: dict, urls: list[str]) -> dict:
    """Abre cada post no Facebook do Daniel e lê texto, autor e grupo. {url: {...}}"""
    if not urls:
        return {}
    script = navegador.PRELUDIO + f"""
LER = {json.dumps(LER_POST_JS)}
out = {{}}
for i, u in enumerate({repr(list(urls))}):
    if i == 0:
        _aba("https://www.facebook.com", u)
    else:
        goto_url(u)
    wait_for_load(); time.sleep(random.uniform(4, 6))
    js(LER); time.sleep(1)
    out[u] = js(LER)
    time.sleep(random.uniform(3, 6))
_fim(out)
"""
    return navegador.rodar(script, cfg, timeout=60 + 20 * len(urls), perfil="facebook")


def coletar(cfg: dict, buscas: list[str] | None = None) -> list[dict]:
    """Resultados no mesmo formato do coletor do Facebook: {autor, perfil, post, grupo, texto, busca, rede}."""
    from .sinais import rede_da_url
    achados = buscar(cfg, buscas)
    fb = [r["url"] for r in achados if eh_permalink_facebook(r["url"])]
    lidos = {}
    try:
        lidos = ler_posts_facebook(cfg, fb[:25])
    except Exception:
        pass  # sem o Facebook do Daniel aberto, fica só com o trecho do Google
    out = []
    for r in achados:
        u = r["url"]
        l = lidos.get(u) or {}
        titulo = re.sub(r"\s*(\.\.\.|…)$", "", r.get("titulo") or "").strip()
        texto = l.get("texto") or f"{titulo}. {r.get('trecho') or ''}".strip()
        out.append({"autor": l.get("autor", ""), "perfil": l.get("perfil", ""),
                    "post": u if (eh_permalink_facebook(u) or "facebook.com" not in u) else "",
                    "grupo": l.get("grupo") or titulo[:90], "texto": texto, "busca": "Google: " + r["busca"],
                    "rede": rede_da_url(u), "lido_no_facebook": bool(l.get("texto"))})
    return out
