"""Banco SQLite local: leads, histórico e lista de não-contatar (LGPD)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta

from .config import DADOS

ETAPAS = [
    ("novo", "Novo"),
    ("qualificado", "Qualificado"),
    ("abordado", "Abordado"),
    ("respondeu", "Respondeu"),
    ("visita", "Visita marcada"),
    ("proposta", "Proposta"),
    ("fechado", "Fechado"),
    ("descartado", "Descartado"),
]
ETAPA_NOME = dict(ETAPAS)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  criado TEXT NOT NULL,
  atualizado TEXT NOT NULL,
  impressao TEXT UNIQUE,
  rede TEXT, url TEXT, autor TEXT, texto TEXT NOT NULL,
  oferta_id TEXT,
  etapa TEXT NOT NULL DEFAULT 'novo',
  score INTEGER, intencao TEXT, analise TEXT,
  mensagem TEXT, notas TEXT DEFAULT '',
  telefone TEXT,
  abordado_em TEXT,
  analisando INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS historico (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id INTEGER, quando TEXT, evento TEXT
);
CREATE TABLE IF NOT EXISTS nao_contatar (
  chave TEXT PRIMARY KEY, quando TEXT, motivo TEXT
);
CREATE TABLE IF NOT EXISTS relatorios (
  id INTEGER PRIMARY KEY AUTOINCREMENT, quando TEXT, itens TEXT, enviado INTEGER DEFAULT 0
);
"""
MIGRACOES = [
    "ALTER TABLE leads ADD COLUMN perfil TEXT",
    "ALTER TABLE leads ADD COLUMN grupo TEXT",
    "ALTER TABLE leads ADD COLUMN relatorio_id INTEGER",
    "ALTER TABLE leads ADD COLUMN numero_relatorio INTEGER",
    "ALTER TABLE leads ADD COLUMN aprovado_em TEXT",
    "ALTER TABLE leads ADD COLUMN recusado_em TEXT",
    "ALTER TABLE leads ADD COLUMN enviado_em TEXT",
    "ALTER TABLE leads ADD COLUMN canal_envio TEXT",
    "ALTER TABLE leads ADD COLUMN erro_envio TEXT",
    "ALTER TABLE leads ADD COLUMN post TEXT",
]


def evento(con, lead_id: int, texto: str):
    con.execute("INSERT INTO historico (lead_id, quando, evento) VALUES (?,?,?)", (lead_id, agora(), texto))
    con.commit()


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def conectar(caminho=None) -> sqlite3.Connection:
    DADOS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho or DADOS / "danyel.db", check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    for m in MIGRACOES:
        try:
            con.execute(m)
        except sqlite3.OperationalError:
            pass  # coluna já existe
    con.commit()
    return con


def impressao(texto: str, url: str) -> str:
    base = " ".join((texto or "").lower().split()) + "|" + (url or "").split("?")[0]
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def chave_contato(url: str, autor: str) -> str:
    return (autor or "").strip().lower() or (url or "").split("?")[0].lower()


def bloqueado(con, url: str, autor: str) -> bool:
    k = chave_contato(url, autor)
    return bool(k) and con.execute("SELECT 1 FROM nao_contatar WHERE chave=?", (k,)).fetchone() is not None


def inserir(con, *, texto, url="", autor="", rede="", oferta_id=None, telefone=None):
    """Retorna (id, novo?). Nunca duplica o mesmo post."""
    imp = impressao(texto, url)
    ja = con.execute("SELECT id FROM leads WHERE impressao=?", (imp,)).fetchone()
    if ja:
        return ja["id"], False
    t = agora()
    cur = con.execute(
        "INSERT INTO leads (criado, atualizado, impressao, rede, url, autor, texto, oferta_id, telefone)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (t, t, imp, rede, url, autor, texto, oferta_id, telefone),
    )
    con.execute("INSERT INTO historico (lead_id, quando, evento) VALUES (?,?,?)", (cur.lastrowid, t, "capturado"))
    con.commit()
    return cur.lastrowid, True


def salvar_analise(con, lead_id: int, analise: dict):
    etapa_atual = con.execute("SELECT etapa FROM leads WHERE id=?", (lead_id,)).fetchone()["etapa"]
    etapa = etapa_atual
    if etapa_atual == "novo":
        etapa = "qualificado" if analise.get("eh_comprador") and analise.get("score", 0) >= 50 else "novo"
        if analise.get("descartar"):
            etapa = "descartado"
    con.execute(
        "UPDATE leads SET score=?, intencao=?, analise=?, mensagem=?, etapa=?, analisando=0, atualizado=? WHERE id=?",
        (int(analise.get("score", 0)), analise.get("intencao", ""), json.dumps(analise, ensure_ascii=False),
         analise.get("mensagem", ""), etapa, agora(), lead_id),
    )
    con.execute("INSERT INTO historico (lead_id, quando, evento) VALUES (?,?,?)",
                (lead_id, agora(), f"analisado: nota {analise.get('score')} – {analise.get('intencao')}"))
    con.commit()


def mudar_etapa(con, lead_id: int, etapa: str):
    if etapa not in ETAPA_NOME:
        raise ValueError(etapa)
    extra = ", abordado_em=?" if etapa == "abordado" else ""
    args = [etapa, agora()] + ([agora()] if extra else []) + [lead_id]
    con.execute(f"UPDATE leads SET etapa=?, atualizado=?{extra} WHERE id=?", args)
    con.execute("INSERT INTO historico (lead_id, quando, evento) VALUES (?,?,?)",
                (lead_id, agora(), f"etapa → {ETAPA_NOME[etapa]}"))
    con.commit()


def bloquear(con, lead_id: int, motivo="pediu para não ser contatado"):
    l = con.execute("SELECT url, autor FROM leads WHERE id=?", (lead_id,)).fetchone()
    con.execute("INSERT OR REPLACE INTO nao_contatar VALUES (?,?,?)", (chave_contato(l["url"], l["autor"]), agora(), motivo))
    con.execute("UPDATE leads SET etapa='descartado', texto='[removido a pedido]', telefone=NULL, mensagem='', analise=NULL, atualizado=? WHERE id=?",
                (agora(), lead_id))
    con.commit()


def retornos(con, dias: int):
    limite = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    return con.execute("SELECT * FROM leads WHERE etapa='abordado' AND abordado_em <= ? ORDER BY abordado_em", (limite,)).fetchall()
