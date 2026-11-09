"""Regras rápidas, sem IA: detectar rede, telefone e sinais de compra.

Servem de filtro antes da IA e de reserva quando a IA está desligada.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


REDES = {
    "facebook.com": "Facebook", "fb.com": "Facebook", "instagram.com": "Instagram",
    "tiktok.com": "TikTok", "olx.com.br": "OLX", "youtube.com": "YouTube",
    "x.com": "X", "twitter.com": "X", "web.whatsapp.com": "WhatsApp", "kwai.com": "Kwai",
    "linkedin.com": "LinkedIn",
}


def rede_da_url(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    for dom, nome in REDES.items():
        if host == dom or host.endswith("." + dom):
            return nome
    return "Outro" if host else "Manual"


_FONE = re.compile(r"(?:\+?55\s*)?\(?\b(1[1-9]|[2-9]\d)\)?\s*9\s?\d{4}[\s.-]?\d{4}\b")


def telefone(texto: str) -> str | None:
    m = _FONE.search(texto or "")
    if not m:
        return None
    d = re.sub(r"\D", "", m.group(0))
    if d.startswith("55") and len(d) >= 12:
        d = d[2:]
    return "55" + d if len(d) == 11 else None


COMPRA = [
    "procuro casa", "procuro uma casa", "procurando casa", "procura-se casa", "procura se casa",
    "quero comprar", "queria comprar", "pretendo comprar", "compro casa", "busco casa",
    "alguem vendendo", "alguem vende", "indicacao de casa", "indicam casa", "interesse em casa",
    "alguem tem casa", "quer comprar", "querem comprar", "estou procurando casa", "to procurando casa",
    "tenho terreno para troca", "troco meu", "troco minha", "procuro imovel", "procuro uma chacara",
]
# Comentários curtos em posts de imóvel ("qual valor?") também são compradores
COMPRA_COMENTARIO = ["quanto custa", "qual o valor", "qual valor", "valor?", "aceita troca?"]
NEGATIVO = {
    "aluguel_procura": ["procuro casa para alugar", "procuro casa pra alugar", "alugo", "para alugar", "pra alugar", "aluga-se"],
    "financiamento": ["financiamento", "financiar", "financiada", "minha casa minha vida", "mcmv", "fgts", "pela caixa"],
    "vendedor": ["vendo casa", "vende-se", "vende casa", "vendo minha casa", "corretor", "creci", "imobiliaria",
                 "a venda", "venda ou troca", "oportunidade", "exclusividade", "estou vendendo", "vendo chacara",
                 "vendo terreno", "valor: r$", "aceita financiamento"],
}


def eh_post_de_vendedor(texto: str) -> bool:
    """Anúncio de quem VENDE (e não pede indicação). Não é guardado."""
    s = sinais(texto)
    return bool(s["negativos"].get("vendedor")) and not any(
        k in s["compra"] for k in ("procuro casa", "procuro uma casa", "quero comprar", "quer comprar", "querem comprar",
                                   "procurando casa", "estou procurando casa", "compro casa", "busco casa"))


def sinais(texto: str, cidades: list[str] | None = None) -> dict:
    t = _norm(texto)
    achados = [s for s in COMPRA if s in t]
    neg = {k: [s for s in v if s in t] for k, v in NEGATIVO.items()}
    neg = {k: v for k, v in neg.items() if v}
    cid = [c for c in (cidades or []) if _norm(c) in t]
    score = min(100, 20 * len(achados) + (20 if cid else 0))
    if "financiamento" in neg:
        score -= 30
    if "aluguel_procura" in neg:
        score -= 50
    if "vendedor" in neg and not achados:
        score -= 40
    return {"compra": achados, "negativos": neg, "cidades": cid, "score": max(0, score)}
