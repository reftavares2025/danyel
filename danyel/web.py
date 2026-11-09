"""Painel do Danyel (http://localhost:5556)."""
from __future__ import annotations

import csv
import io
import json
import threading
from urllib.parse import quote

from flask import Flask, Response, abort, redirect, render_template, request, url_for

from . import caca, cerebro, config, db
from . import sinais as S

app = Flask(__name__)
CFG = config.carregar()
CON = db.conectar()
TRAVA = threading.Lock()


def recarregar_cfg():
    global CFG
    CFG = config.carregar()


def analisar_em_segundo_plano(lead_id: int):
    def tarefa():
        con = db.conectar()
        l = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not l:
            return
        of = config.oferta(CFG, l["oferta_id"])
        res = cerebro.analisar(CFG, of, texto=l["texto"], rede=l["rede"], autor=l["autor"])
        with TRAVA:
            db.salvar_analise(con, lead_id, res)
        con.close()

    with TRAVA:
        CON.execute("UPDATE leads SET analisando=1 WHERE id=?", (lead_id,))
        CON.commit()
    threading.Thread(target=tarefa, daemon=True).start()


def capturar(texto, url="", autor="", oferta_id=None):
    texto = (texto or "").strip()
    if len(texto) < 8:
        return None, "Texto muito curto."
    if db.bloqueado(CON, url, autor):
        return None, "Essa pessoa pediu para não ser contatada."
    with TRAVA:
        lid, novo = db.inserir(CON, texto=texto, url=url, autor=autor, rede=S.rede_da_url(url),
                               oferta_id=oferta_id or (CFG["ofertas"][0]["id"] if CFG["ofertas"] else None),
                               telefone=S.telefone(texto))
    if novo:
        analisar_em_segundo_plano(lid)
    return lid, None if novo else "Esse post já estava no Danyel."


@app.before_request
def _so_local():
    """Só aceita gravação vinda do próprio painel: um site qualquer aberto no
    seu Chrome não consegue enfiar dados ou mudar o funil (proteção CSRF).
    Também recusa Host diferente de localhost/127.0.0.1 (proteção contra DNS rebinding,
    que deixaria um site externo ler o /exportar.csv com os leads)."""
    if request.host.split(":")[0] not in ("localhost", "127.0.0.1"):
        abort(403)
    if request.method == "POST":
        origem = request.headers.get("Origin") or request.headers.get("Referer") or ""
        if origem and not origem.startswith((f"http://localhost:{request.host.split(':')[-1]}",
                                              f"http://127.0.0.1:{request.host.split(':')[-1]}")):
            abort(403)


@app.template_filter("json")
def _json(s):
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


@app.template_filter("wa")
def _wa(lead):
    if not lead["telefone"]:
        return ""
    return f"https://wa.me/{lead['telefone']}?text={quote(lead['mensagem'] or '')}"


@app.context_processor
def _ctx():
    return {"ETAPAS": db.ETAPAS, "ETAPA_NOME": db.ETAPA_NOME, "CFG": CFG}


@app.get("/")
def inicio():
    etapa = request.args.get("etapa", "")
    rede = request.args.get("rede", "")
    sql, args = "SELECT * FROM leads WHERE 1=1", []
    if etapa:
        sql += " AND etapa=?"; args.append(etapa)
    else:
        sql += " AND etapa NOT IN ('descartado')"
    if rede:
        sql += " AND rede=?"; args.append(rede)
    sql += " ORDER BY (etapa='novo' AND score IS NULL) DESC, score DESC, criado DESC"
    leads = CON.execute(sql, args).fetchall()
    contagem = {r["etapa"]: r["n"] for r in CON.execute("SELECT etapa, COUNT(*) n FROM leads GROUP BY etapa")}
    redes = [r["rede"] for r in CON.execute("SELECT DISTINCT rede FROM leads WHERE rede IS NOT NULL")]
    retorno = db.retornos(CON, int(CFG["painel"].get("dias_para_retorno", 2)))
    return render_template("inicio.html", leads=leads, contagem=contagem, etapa=etapa, rede=rede,
                           redes=redes, retorno=retorno)


@app.get("/lead/<int:lid>")
def lead(lid):
    l = CON.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone() or abort(404)
    hist = CON.execute("SELECT * FROM historico WHERE lead_id=? ORDER BY id DESC", (lid,)).fetchall()
    return render_template("lead.html", l=l, hist=hist)


@app.post("/lead/<int:lid>")
def lead_salvar(lid):
    acao = request.form.get("acao")
    with TRAVA:
        if acao == "salvar":
            CON.execute("UPDATE leads SET mensagem=?, notas=?, autor=?, telefone=?, atualizado=? WHERE id=?",
                        (request.form.get("mensagem", ""), request.form.get("notas", ""), request.form.get("autor", ""),
                         S.telefone(request.form.get("telefone", "")) or None, db.agora(), lid))
            CON.commit()
        elif acao == "etapa":
            db.mudar_etapa(CON, lid, request.form["etapa"])
        elif acao == "bloquear":
            db.bloquear(CON, lid)
    if acao == "reanalisar":
        analisar_em_segundo_plano(lid)
    return redirect(url_for("lead", lid=lid))


@app.route("/novo", methods=["GET", "POST"])
def novo():
    erro = None
    if request.method == "POST":
        lid, erro = capturar(request.form.get("texto"), request.form.get("url", ""), request.form.get("autor", ""),
                             request.form.get("oferta_id"))
        if lid:
            return redirect(url_for("lead", lid=lid))
    return render_template("novo.html", erro=erro, pre=request.values, popup=False)


@app.route("/capturar", methods=["GET", "POST"])
def capturar_popup():
    """Destino do botão 'Danyel' do navegador (abre numa janelinha)."""
    if request.method == "POST":
        lid, erro = capturar(request.form.get("texto"), request.form.get("url", ""), request.form.get("autor", ""),
                             request.form.get("oferta_id"))
        return render_template("capturado.html", lid=lid, erro=erro, popup=True)
    return render_template("novo.html", erro=None, pre=request.values, popup=True)


@app.post("/importar")
def importar():
    """Cola vários posts de uma vez, separados por uma linha com ---"""
    blocos = [b.strip() for b in request.form.get("lote", "").split("\n---") if b.strip()]
    n = 0
    for b in blocos:
        linhas = b.splitlines()
        url = linhas[0].strip() if linhas and linhas[0].strip().startswith("http") else ""
        texto = "\n".join(linhas[1:] if url else linhas)
        lid, erro = capturar(texto, url)
        n += 1 if lid and not erro else 0
    return redirect(url_for("inicio"))


@app.get("/cacar")
def cacar():
    recarregar_cfg()
    porta = CFG["painel"].get("porta", 5556)
    bookmarklet = (
        "javascript:(()=>{let s=String(getSelection()).trim();"
        "if(!s)s=prompt('Danyel: cole ou digite o texto do post/comentário');if(!s)return;"
        f"window.open('http://localhost:{porta}/capturar?'+new URLSearchParams({{texto:s.slice(0,6000),url:location.href}}),"
        "'danyel','width=540,height=720')})()"
    )
    return render_template("cacar.html", itens=caca.rota(CFG), bookmarklet=bookmarklet)


@app.get("/exportar.csv")
def exportar():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["id", "criado", "rede", "autor", "url", "etapa", "score", "intencao", "telefone", "texto", "mensagem", "notas"])
    def seguro(v):
        # texto de post vem de estranhos: "=HYPERLINK(...)" viraria fórmula no Excel
        s = "" if v is None else str(v)
        return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s

    for l in CON.execute("SELECT * FROM leads ORDER BY id"):
        w.writerow([seguro(v) for v in (l["id"], l["criado"], l["rede"], l["autor"], l["url"], l["etapa"], l["score"],
                    l["intencao"], l["telefone"], l["texto"], l["mensagem"], l["notas"])])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=danyel-leads.csv"})


def rodar(porta: int | None = None):
    app.run(host="127.0.0.1", port=porta or CFG["painel"].get("porta", 5556), debug=False)
