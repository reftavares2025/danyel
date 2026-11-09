"""Varredura automática do Facebook com a sua conta: só LEITURA.

Faz as buscas de posts do dia em ritmo humano (pausas aleatórias, poucas
buscas) e devolve autor, link do perfil, grupo e texto de cada post.
"""
from __future__ import annotations

import json
from urllib.parse import quote

from . import navegador

EXTRATOR_JS = r"""
(() => {
  for (const b of document.querySelectorAll('div[role="button"]')) {
    if ((b.innerText||'').trim() === 'Ver mais') { try { b.click(); } catch(e){} }
  }
  const out=[], vistos=new Set();
  for (const el of document.querySelectorAll('div[aria-posinset], div[role="article"], div[aria-describedby]')) {
    const msgs=[...el.querySelectorAll('[data-ad-rendering-role="story_message"], [data-ad-preview="message"], div[dir="auto"]')]
      .map(d=>d.innerText.trim()).filter(t=>t.length>15);
    const texto=[...new Set(msgs)].sort((a,b)=>b.length-a.length)[0]||'';
    if(!texto) continue;
    const k=texto.slice(0,80); if(vistos.has(k)) continue; vistos.add(k);
    const perfis=[...el.querySelectorAll('a[href*="facebook.com/"]')]
      .filter(a=>/profile\.php\?id=|facebook\.com\/(?!search|groups|photo|watch|hashtag|reel|events|pages|story)[A-Za-z0-9.]{3,}(\/|\?|$)|\/groups\/[^/]+\/user\/\d+/.test(a.href) && (a.innerText||'').trim().length>1);
    const p=perfis[0];
    let perfil='';
    if(p){ const u=new URL(p.href); perfil = u.pathname==='/profile.php' ? 'https://www.facebook.com/profile.php?id='+u.searchParams.get('id') : 'https://www.facebook.com'+u.pathname; }
    const titulo=((el.querySelector('h2, h3, h4, strong')||{}).innerText||'').split('\n')[0].trim();
    const lp=[...el.querySelectorAll('a[href]')].map(a=>a.href).filter(h=>!/\/search\//.test(h))
      .find(h=>/\/posts\/|\/permalink\/|story_fbid=|multi_permalinks=|\/permalink\.php|\/videos\/\d|\/reel\/\d/.test(h));
    let post='';
    if(lp){ const u=new URL(lp); const g=u.pathname.match(/\/groups\/([^/]+)/), mp=u.searchParams.get('multi_permalinks');
      if(g && mp) post='https://www.facebook.com/groups/'+g[1]+'/permalink/'+mp.split(',')[0]+'/';
      else { [...u.searchParams.keys()].filter(k=>k.startsWith('__')||['comment_id','ref','hoisted_section_header_type'].includes(k)).forEach(k=>u.searchParams.delete(k)); post=u.toString(); } }
    out.push({autor:p?(p.innerText||'').trim().split('\n')[0]:'', perfil, post, grupo:titulo.slice(0,90), texto:texto.replace(/\s*Ver mais$/,'').slice(0,3000)});
  }
  return JSON.stringify(out);
})()
"""


def montar_buscas(cfg: dict, n: int = 4) -> list[str]:
    from datetime import date, datetime
    caca = cfg.get("caca", {})
    frases = caca.get("frases_facebook") or ["quero comprar casa", "compro casa", "procuro casa para comprar",
                                              "alguém vendendo casa", "procuro casa com edícula", "alguém tem casa à venda"]
    cidades = caca.get("cidades") or ["Cosmópolis"]
    # meio-dia em diante gira diferente da manhã, para os 2 ciclos do dia não repetirem
    d = date.today().toordinal() * 2 + (1 if datetime.now().hour >= 12 else 0)
    buscas = []
    for i in range(n):
        frase = frases[(d + i) % len(frases)]
        cidade = cidades[0] if i == 0 else cidades[(d + i * 3) % len(cidades)]  # sempre 1 busca em Cosmópolis
        buscas.append(f"{frase} {cidade}")
    return list(dict.fromkeys(buscas))


def coletar(cfg: dict, buscas: list[str] | None = None) -> list[dict]:
    buscas = buscas or montar_buscas(cfg, int(cfg.get("robo", {}).get("buscas_por_ciclo", 4)))
    script = navegador.PRELUDIO + f"""
from urllib.parse import quote
EXTR = {json.dumps(EXTRATOR_JS)}
resultado = []
for i, q in enumerate({repr(list(buscas))}):
    url = "https://www.facebook.com/search/posts/?q=" + quote(q)
    if i == 0:
        _aba("https://www.facebook.com", url)
    else:
        goto_url(url)
    wait_for_load(); time.sleep(random.uniform(4, 7))
    for _ in range(3):
        js("window.scrollBy(0, 1800 + Math.random()*900)"); time.sleep(random.uniform(2, 4))
    js(EXTR); time.sleep(1.5)
    # O Facebook só revela o link do post (na data) quando o mouse passa em cima:
    # passa o mouse de verdade, um por um, em cada link escondido.
    # link da data ainda escondido: href relativo ("?__cft__..." ou "#") dentro de um post
    total = js("(() => {{ let n=0; document.querySelectorAll('div[aria-posinset] a[href], div[role=article] a[href]').forEach(a=>{{ const h=a.getAttribute('href')||''; if(/^[?#]/.test(h) || h.includes('/search/posts/')) a.setAttribute('data-dy', n++); }}); return n; }})()") or 0
    try:
        cdp("Emulation.setFocusEmulationEnabled", enabled=True)  # janela em segundo plano também recebe o mouse
    except Exception:
        pass
    for k in range(min(int(total), 40)):
        pos = js("(() => {{ const a=document.querySelector('a[data-dy=\\"%d\\"]'); if(!a) return null; a.scrollIntoView({{block:'center'}}); const r=a.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; }})()" % k)
        if not pos:
            continue
        time.sleep(0.25)
        cdp("Input.dispatchMouseEvent", type="mouseMoved", x=pos[0], y=pos[1])
        time.sleep(random.uniform(0.35, 0.7))
    time.sleep(1)
    for p in json.loads(js(EXTR)):
        p["busca"] = q
        resultado.append(p)
    time.sleep(random.uniform(6, 12))
_fim(resultado)
"""
    return navegador.rodar(script, cfg, timeout=900, perfil="facebook")
