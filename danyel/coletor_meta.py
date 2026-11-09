"""Coleta potenciais compradores dentro do Meta do aprovador (Daniel), pela API
oficial com o token dele: mensagens recebidas nas páginas (Messenger) e
comentários no Instagram (posts e anúncios).

Páginas de saúde (Croad, Green Home) ficam de fora: são dados sensíveis de
saúde (LGPD, art. 11) e não têm relação com a venda da casa.
"""
from __future__ import annotations

import re
from pathlib import Path

import requests

V = "https://graph.facebook.com/v21.0/"
PADRAO = {
    "token_arquivo": r"C:\caminho\para\token_meta.txt",
    "conta": "act_SEU_ID_DE_CONTA",
    "paginas": ["Nome da Sua Página"],
    "dias": 365,
}


def _token(cfg) -> str:
    arq = Path((cfg.get("meta") or {}).get("token_arquivo") or PADRAO["token_arquivo"])
    achados = re.findall(r"EAA[A-Za-z0-9]+", arq.read_text(encoding="utf-8", errors="ignore"))
    if not achados:
        raise RuntimeError(f"token não encontrado em {arq}")
    return achados[-1]


def _get(caminho, token, **q):
    q["access_token"] = token
    r = requests.get(caminho if caminho.startswith("http") else V + caminho, params=q, timeout=60).json()
    if "error" in r:
        raise RuntimeError(r["error"].get("message", "erro"))
    return r


def _todos(caminho, token, maximo=300, **q):
    out, r = [], _get(caminho, token, **q)
    while True:
        out += r.get("data", [])
        nxt = (r.get("paging") or {}).get("next")
        if not nxt or len(out) >= maximo:
            return out
        r = requests.get(nxt, timeout=60).json()


IMOVEL = re.compile(r"\b(casas?|im[oó]ve(l|is)|terrenos?|ch[aá]caras?|ed[ií]cula|lote|sobrado|apartamento|apto|"
                    r"quartos?|dormit[oó]rios?|su[ií]te|metragem|escritura|bairro|onde fica)\b", re.I)


def _usuario(c) -> str:
    u = c.get("username") or (c.get("from") or {}).get("username") or ""
    return "@" + u if u else "Usuário do Instagram"


def de_imovel(item, pagina_imoveis="Nome da Sua Página") -> bool:
    """Só interessa o que fala de imóvel: o resto (carro, spam, elogio) não é comprador da casa."""
    return pagina_imoveis in item["grupo"] or bool(IMOVEL.search(item["texto"] + " " + item["grupo"]))


def coletar(cfg) -> tuple[list[dict], list[str]]:
    """Retorna (itens, fontes). Cada item: texto, autor, perfil, grupo, url, rede."""
    m = {**PADRAO, **(cfg.get("meta") or {})}
    tok = _token(cfg)
    paginas = [p for p in _todos("me/accounts", tok, fields="id,name,access_token,instagram_business_account{id,username}")
               if p["name"] in m["paginas"]]
    itens, fontes = [], []
    for p in paginas:
        pt, nome = p["access_token"], p["name"]
        # 1) Mensagens recebidas na página (Messenger)
        try:
            convs = _todos(f"{p['id']}/conversations", pt, maximo=100,
                           fields="link,updated_time,participants,messages.limit(8){message,from,created_time}")
            for c in convs:
                cliente = [x for x in (c.get("participants") or {}).get("data", []) if x.get("id") != p["id"]]
                if not cliente:
                    continue
                falas = [x for x in (c.get("messages") or {}).get("data", [])
                         if (x.get("from") or {}).get("id") != p["id"] and x.get("message")]
                if not falas:
                    continue
                itens.append({"texto": " / ".join(reversed([f["message"] for f in falas]))[:1500],
                              "autor": cliente[0].get("name", ""), "perfil": "",
                              "grupo": f"Mensagem na página {nome} ({c.get('updated_time','')[:10]})",
                              "url": "https://business.facebook.com/latest/inbox/all", "rede": "Messenger (página)"})
            fontes.append(f"mensagens da página {nome}")
        except Exception as e:
            fontes.append(f"mensagens da página {nome}: indisponível ({str(e)[:60]})")
        # 2) Comentários no Instagram da página (posts e anúncios)
        ig = p.get("instagram_business_account")
        if ig:
            try:
                midias = _todos(f"{ig['id']}/media", pt, maximo=100, fields="id,caption,permalink,comments_count")
                for md in [x for x in midias if x.get("comments_count")]:
                    for c in _todos(f"{md['id']}/comments", pt, fields="id,username,from,text,timestamp"):
                        itens.append({"texto": c.get("text", ""), "autor": _usuario(c),
                                      "perfil": "", "url": md.get("permalink", ""), "rede": "Instagram",
                                      "grupo": f"Comentário no Instagram @{ig['username']} – post: "
                                               f"\"{(md.get('caption') or '')[:70]}\""})
                fontes.append(f"comentários do Instagram @{ig['username']}")
            except Exception as e:
                fontes.append(f"Instagram @{ig.get('username')}: indisponível ({str(e)[:60]})")
    # 3) Comentários de Instagram nos anúncios da conta (dark posts não aparecem em /media)
    try:
        pt_por_pag = {p["id"]: p["access_token"] for p in paginas}
        vistos = set()
        for ad in _todos(f"{m['conta']}/ads", tok, maximo=300,
                         fields="name,creative{effective_object_story_id,effective_instagram_media_id}"):
            cr = ad.get("creative") or {}
            igm, sid = cr.get("effective_instagram_media_id"), cr.get("effective_object_story_id") or ""
            pt = pt_por_pag.get(sid.split("_")[0])
            if not igm or not pt or igm in vistos:
                continue
            vistos.add(igm)
            for c in _todos(f"{igm}/comments", pt, fields="id,username,from,text,timestamp"):
                itens.append({"texto": c.get("text", ""), "autor": _usuario(c), "perfil": "",
                              "url": (f"https://www.instagram.com/{_usuario(c)[1:]}/" if _usuario(c).startswith("@") else ""), "rede": "Instagram",
                              "grupo": f"Comentário no anúncio \"{ad.get('name','')}\""})
        fontes.append("comentários nos anúncios")
    except Exception as e:
        fontes.append(f"anúncios: indisponível ({str(e)[:60]})")
    # sem duplicar o mesmo comentário visto como post e como anúncio
    unicos, chaves = [], set()
    for i in itens:
        k = (i["autor"], i["texto"][:200])
        if i["texto"].strip() and k not in chaves and de_imovel(i):
            chaves.add(k); unicos.append(i)
    return unicos, fontes
