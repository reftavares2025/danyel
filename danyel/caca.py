"""Rota de caça do dia: buscas prontas nas redes, para abrir com a SUA conta.

O Danyel não entra nas redes sozinho (isso viola os termos delas e pode
bloquear seu perfil). Ele monta as buscas certas, você abre, e o que for
comprador você manda para ele com o botão "Danyel" do navegador.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import quote


def _q(t: str) -> str:
    return quote(t, safe="")


def rota(cfg: dict, dia: date | None = None) -> list[dict]:
    caca = cfg.get("caca", {})
    cidades = caca.get("cidades") or ["Cosmópolis"]
    frases = caca.get("frases") or ["procuro casa"]
    tags = caca.get("hashtags") or []
    dia = dia or date.today()
    n = dia.toordinal()
    # gira as combinações a cada dia, para não repetir sempre a mesma busca
    hoje_fr = [frases[(n + i) % len(frases)] for i in range(min(3, len(frases)))]
    hoje_cid = [cidades[(n + i) % len(cidades)] for i in range(min(3, len(cidades)))]
    hoje_cid = list(dict.fromkeys([cidades[0]] + hoje_cid))

    itens: list[dict] = []
    for c in hoje_cid:
        for f in hoje_fr[:2]:
            itens.append({"rede": "Facebook", "rotulo": f'Posts: "{f}" {c}',
                          "url": f"https://www.facebook.com/search/posts/?q={_q(f + ' ' + c)}",
                          "dica": "Filtre por 'Posts recentes'. Grupos de compra e venda da cidade são a mina de ouro."})
        itens.append({"rede": "Facebook", "rotulo": f"Grupos de imóveis em {c}",
                      "url": f"https://www.facebook.com/search/groups/?q={_q('imóveis ' + c)}",
                      "dica": "Entre nos grupos e procure posts de quem PROCURA casa (não de quem vende)."})
        itens.append({"rede": "TikTok", "rotulo": f"Vídeos de casa à venda em {c}",
                      "url": f"https://www.tiktok.com/search?q={_q('casa à venda ' + c)}",
                      "dica": "Abra os comentários: quem pergunta 'qual valor?' ou 'aceita troca?' está comprando."})
        itens.append({"rede": "Instagram", "rotulo": f"Busca: casa à venda {c}",
                      "url": f"https://www.instagram.com/explore/search/keyword/?q={_q('casa à venda ' + c)}",
                      "dica": "Nos posts de imobiliárias da região, os comentários 'valor?' são compradores ativos."})
        itens.append({"rede": "X", "rotulo": f'"{hoje_fr[0]}" {c}',
                      "url": f"https://x.com/search?q={_q(hoje_fr[0] + ' ' + c)}&f=live", "dica": ""})
        itens.append({"rede": "Google", "rotulo": f'Google: "{hoje_fr[0]}" {c} em redes',
                      "url": "https://www.google.com/search?q=" + _q(f'"{hoje_fr[0]}" "{c}" (site:facebook.com OR site:instagram.com OR site:tiktok.com)') + "&tbs=qdr:m",
                      "dica": "Resultados do último mês."})
    for t in tags[:4]:
        itens.append({"rede": "Instagram", "rotulo": f"#{t}", "url": f"https://www.instagram.com/explore/tags/{_q(t)}/",
                      "dica": "Veja os posts recentes e os comentários."})
    itens.append({"rede": "OLX", "rotulo": "OLX: anúncios de procura em Cosmópolis",
                  "url": "https://www.olx.com.br/imoveis/estado-sp/grande-campinas/cosmopolis?q=procuro",
                  "dica": "Pouco volume, mas quem anuncia 'procuro' é comprador decidido."})
    return itens
