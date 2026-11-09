"""Robô automático do Danyel.

ciclo()       Varre o Facebook, analisa com IA e manda o relatório no WhatsApp
              do aprovador (Daniel) com cópia para o Régis.
aprovacoes()  Lê a resposta do Daniel ("APROVO 1 3", "APROVO TODOS", "NÃO 2")
              e envia as mensagens aprovadas, respeitando as travas.

Travas: nada vai para desconhecido sem aprovação; limite diário total e por
canal; só em horário comercial; quem pediu para não ser contatado nunca entra.
"""
from __future__ import annotations

import json
import re
import traceback
from datetime import date, datetime, timedelta

from . import cerebro, config, db, whatsapp
from . import sinais as S
from .config import DADOS


def log(msg: str):
    DADOS.mkdir(parents=True, exist_ok=True)
    linha = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(linha)
    with open(DADOS / "robo.log", "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def _rcfg(cfg):
    r = {"aprovador_nome": "Daniel", "aprovador_whatsapp": "", "copia_whatsapp": "", "nota_minima": 60,
         "limite_total_dia": 10, "limite_facebook_dia": 5, "horario": [8, 20], "buscas_por_ciclo": 4,
         "avisar_quando_vazio": True}
    r.update(cfg.get("robo") or {})
    return r


def _avisar(cfg, texto: str, para_aprovador=True):
    r = _rcfg(cfg)
    destinos = ([r["aprovador_whatsapp"]] if para_aprovador else []) + [r["copia_whatsapp"]]
    for i, n in enumerate([d for d in destinos if d]):
        prefixo = "" if (para_aprovador and i == 0) else ("📋 *Cópia – enviado ao " + r["aprovador_nome"] + "*\n\n" if para_aprovador else "")
        try:
            whatsapp.enviar(cfg, n, prefixo + texto)
        except Exception as e:
            log(f"falha ao avisar {n}: {e}")


def _canal(lead) -> str:
    if lead["telefone"]:
        return "WhatsApp"
    if lead["perfil"]:
        return "Messenger"
    return "manual"


def _link_busca(q: str) -> str:
    from urllib.parse import quote
    return "https://www.facebook.com/search/posts/?q=" + quote(q) if q else ""


def _sem_links(t: str) -> str:
    """A sugestão de conversa vai para o Daniel usar; sem mandar o lead para site."""
    t = re.sub(r"\s*(Fotos aqui:|Veja as fotos:|Fotos:)?\s*https?://\S+\s*\.?", " ", t or "")
    return re.sub(r"\s{2,}", " ", t).strip()


def _curto(t: str, n: int) -> str:
    t = re.sub(r"\s+", " ", _sem_links(t or "")).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def _link_post_por_texto(l) -> str:
    """Sem o link próprio do post: uma busca no Facebook pelo começo do texto abre o post no topo.
    Mensagem de página, Instagram e perfil usam o link que tiverem."""
    url = l["url"] or ""
    if l["rede"] in ("Instagram", "Messenger (página)") or "facebook.com/l.php" in url:
        return "" if "facebook.com/l.php" in url else url
    palavras = re.sub(r"[^\w\sà-ÿ]", " ", (l["texto"] or "")).split()
    if len(palavras) >= 4:
        return _link_busca(" ".join(palavras[:9]))
    return l["perfil"] or url


def _contato_direto(cfg) -> bool:
    return _rcfg(cfg).get("modo") != "robo_envia"


def _bloco_contato(l, nota_minima) -> list[str]:
    """Modo padrão: o Daniel entra em contato. Vai o link do post e o WhatsApp clicável."""
    a = json.loads(l["analise"] or "{}")
    recomendo = l["etapa"] == "qualificado" and (l["score"] or 0) >= nota_minima
    texto = (l["texto"] or "").strip()
    post = l["post"] if "post" in l.keys() else ""
    motivo = _curto(a.get("motivo") or "nota abaixo do mínimo", 170)
    linhas = [
        f"*{l['numero_relatorio']}) {l['autor'] or 'Sem nome'}* – nota {l['score']} – {l['grupo'] or l['rede']}",
        f"🧠 {_curto(a.get('resumo') or texto, 150)}",
        (f"✅ {motivo}" if recomendo else f"⚠️ Não escolheria: {motivo}"),
    ]
    if l["telefone"]:
        linhas.append(f"📞 https://wa.me/{l['telefone']}")
    if post and "/search/posts/#" in post:
        post = ""  # link interno da busca, não abre o post
    link = post or _link_post_por_texto(l)
    if link:
        linhas.append(f"🔗 {link}")
    return linhas + [""]


def _bloco(l, nota_minima) -> list[str]:
    a = json.loads(l["analise"] or "{}")
    canal = _canal(l)
    recomendo = l["etapa"] == "qualificado" and (l["score"] or 0) >= nota_minima
    origem = l["grupo"] or l["rede"]
    texto = (l["texto"] or "").strip()
    if canal == "manual":
        envio = "📲 Sem contato direto: *você* responde por " + (
            "Messenger da página" if "Mensagem na página" in origem else
            "Instagram (no próprio comentário)" if l["rede"] == "Instagram" else "comentário no post")
    else:
        envio = f"📲 Vou mandar por: *{canal}*" + (f" ({l['telefone']})" if l["telefone"] else "")
    return [
        f"*{l['numero_relatorio']}) {l['autor'] or 'Sem nome'}* – nota {l['score']}/100",
        f"📍 {origem}",
        f"🧠 {a.get('resumo') or '-'}",
        f"💬 \"{texto[:220]}{'…' if len(texto) > 220 else ''}\"",
        (f"✅ Por que eu escolhi: {a.get('motivo', '')}" if recomendo else
         f"⚠️ Por que eu *não* escolheria: {a.get('motivo') or 'nota abaixo do mínimo'}"),
        f"🔗 {l['perfil'] or l['url'] or '-'}",
        envio,
        f"✉️ Mensagem: \"{l['mensagem']}\"", "",
    ]


def montar_relatorio(cfg, leads, buscas) -> str:
    r = _rcfg(cfg)
    nm = int(r["nota_minima"])
    hoje = date.today().strftime("%d/%m")
    bons = [l for l in leads if l["etapa"] == "qualificado" and (l["score"] or 0) >= nm]
    if _contato_direto(cfg):
        linhas = [f"🤖 *Danyel – {len(leads)} {'possível comprador' if len(leads) == 1 else 'possíveis compradores'} "
                  f"({hoje})*",
                  f"{r['aprovador_nome']}, achei nas redes. Toque no 📞 para chamar no WhatsApp ou no 🔗 para abrir "
                  "o post e falar com a pessoa. Só mando quem tem perfil de comprador da casa "
                  "(à vista ou troca); o resto eu descarto.", ""]
    else:
        linhas = [f"🤖 *Danyel – potenciais compradores ({hoje})*",
              f"Olá {r['aprovador_nome']}! Procurei em: {'; '.join(buscas)}.",
              f"Achei *{len(leads)}* {'pessoa' if len(leads) == 1 else 'pessoas'}: *{len(bons)}* com nota boa "
              f"(a partir de {nm}) e *{len(leads) - len(bons)}* abaixo da nota. Mando todas para *você decidir*, "
              "com a nota e o motivo de cada uma.", ""]
    bloco = _bloco_contato if _contato_direto(cfg) else _bloco
    if bons:
        linhas += ["━━ ✅ *RECOMENDO* ━━", ""]
        for l in bons:
            linhas += bloco(l, nm)
    resto = [l for l in leads if l not in bons]
    if resto:
        linhas += ["━━ ⚠️ *ABAIXO DA NOTA – VOCÊ DECIDE* ━━", ""]
        for l in resto:
            linhas += bloco(l, nm)
    if _contato_direto(cfg):
        linhas += ["_Eu não mando nada para essas pessoas: o contato é seu._"]
    else:
        linhas += ["Para aprovar, responda aqui:", "*APROVO TODOS*  ou  *APROVO 1 3*", "Para recusar: *NÃO 2*",
                   "_Nada é enviado sem a sua aprovação._"]
    return "\n".join(linhas)


_VENDEDOR = re.compile(r"\b(estou|to|tô|t[oô]\s+)?\s*vendendo\s+(a\s+)?(minha|meu|uma|essa|esta)\b|\bvendo\s+(a\s+)?(minha|meu)\b"
                       r"|\bvende-se\b|\bà venda por\b|\bconfira (esse|este) im[oó]vel\b|\bquer comprar\?", re.I)


def vale_a_pena(l, nota_min: int) -> bool:
    """Filtro do Régis (07/11/2026): só vai para o aprovador quem REALMENTE pode comprar.
    Comprador qualificado, nota mínima, quer comprar/trocar/investir e não depende de
    financiamento (a casa é só à vista ou troca). O resto é descartado em silêncio."""
    a = json.loads(l["analise"] or "{}")
    if _VENDEDOR.search(l["texto"] or "") or S.eh_post_de_vendedor(l["texto"] or ""):
        return False
    return (l["etapa"] == "qualificado" and bool(a.get("eh_comprador")) and (l["score"] or 0) >= nota_min
            and (a.get("intencao") or "") in ("compra", "troca", "investimento")
            and (a.get("forma_pagamento") or "") != "financiamento")


def _pode_comentar(l, nota_min: int) -> bool:
    """Só comenta em post de quem PROCURA casa: nada de aluguel, vendedor ou anúncio de corretor."""
    a = json.loads(l["analise"] or "{}")
    return (l["rede"] == "Facebook" and vale_a_pena(l, nota_min) and (l["score"] or 0) >= nota_min
            and (a.get("intencao") or "") not in ("aluguel", "vendedor", "outro") and not l["canal_envio"])


def comentar_leads(cfg, con, cand) -> list:
    """Comenta direto (sem aprovação, pedido do Daniel em 04/11) com o WhatsApp dele."""
    import random
    import time
    from . import comentador
    r = _rcfg(cfg)
    limite = int(r.get("limite_comentarios_dia", 8))
    feitos = []
    for l in cand:
        if not _pode_comentar(l, int(r.get("nota_minima_comentario", 15))):
            continue
        if _enviados_hoje(con, "comentário") >= limite:
            log("comentários: limite diário atingido"); break
        try:
            res = comentador.comentar(cfg, dict(l))
        except Exception as e:
            res = {"ok": False, "motivo": str(e)[:200]}
        if res.get("post"):
            con.execute("UPDATE leads SET post=? WHERE id=?", (res["post"], l["id"]))
        if res.get("ok"):
            con.execute("UPDATE leads SET enviado_em=?, canal_envio='comentário', notas=? WHERE id=?",
                        (db.agora(), res.get("comentario") or res.get("post"), l["id"]))
            db.evento(con, l["id"], f"comentário publicado: {res.get('comentario') or res.get('post')}")
            feitos.append((l, res.get("comentario") or res.get("post")))
            log(f"comentado lead {l['id']}: {res.get('comentario')}")
        else:
            con.execute("UPDATE leads SET erro_envio=? WHERE id=?", ("comentário: " + (res.get("motivo") or "?"), l["id"]))
            log(f"não comentei lead {l['id']}: {res.get('motivo')}")
        con.commit()
        time.sleep(random.uniform(60, 120))  # ritmo humano entre comentários
    return feitos


def montar_comentados(cfg, comentados, resto) -> str:
    r = _rcfg(cfg)
    nm = int(r["nota_minima"])
    hoje = date.today().strftime("%d/%m")
    linhas = [f"💬 *Danyel – comentei com o WhatsApp do Daniel ({hoje})*", ""]
    for i, (l, link) in enumerate(comentados, 1):
        linhas += [f"{i}) {l['autor'] or 'Sem nome'} – {l['grupo'] or l['rede']}", f"🔗 {link}", ""]
    if resto:
        linhas += ["📋 *Outros compradores (não consegui comentar no post: fale direto)*", ""]
        for i, l in enumerate(resto, len(comentados) + 1):
            l = dict(l); l["numero_relatorio"] = i
            linhas += _bloco_contato(_Linha(l), nm)
    return "\n".join(linhas).strip()


class _Linha(dict):
    def keys(self):
        return super().keys()


def ciclo(cfg=None, enviar=True) -> dict:
    from . import coletor_facebook
    cfg = cfg or config.carregar()
    r = _rcfg(cfg)
    con = db.conectar()
    oferta = config.oferta(cfg, None)
    buscas = coletor_facebook.montar_buscas(cfg, int(r["buscas_por_ciclo"]))
    log(f"ciclo: buscas {buscas}")
    posts = coletor_facebook.coletar(cfg, buscas)
    log(f"ciclo: {len(posts)} posts lidos")

    novos = []
    for p in posts:
        texto = (p.get("texto") or "").strip()
        regra = S.sinais(texto, cfg.get("caca", {}).get("cidades"))
        # só guarda e analisa quem tem sinal de COMPRA; o resto nem é armazenado (LGPD)
        if not regra["compra"] or regra["negativos"].get("aluguel_procura") or S.eh_post_de_vendedor(texto):
            continue
        if db.bloqueado(con, p.get("perfil", ""), p.get("autor", "")):
            continue
        lid, novo = db.inserir(con, texto=texto, url=p.get("perfil", ""), autor=p.get("autor", ""),
                               rede="Facebook", oferta_id=oferta.get("id"), telefone=S.telefone(texto))
        link_post = p.get("post") or ""
        if not novo:
            if link_post:
                con.execute("UPDATE leads SET post=? WHERE id=? AND COALESCE(post,'')=''", (link_post, lid))
                con.commit()
            continue
        con.execute("UPDATE leads SET perfil=?, grupo=?, post=? WHERE id=?",
                    (p.get("perfil", ""), p.get("grupo", ""), link_post or _link_busca(p.get("busca", "")), lid))
        con.commit()
        res = cerebro.analisar(cfg, oferta, texto=texto, rede="Facebook", autor=p.get("autor", ""))
        if res.get("mensagem") and not whatsapp.texto_integro(res["mensagem"]):
            res["mensagem"] = cerebro.mensagem_padrao(cfg, oferta)  # nunca manda texto com acento quebrado
        db.salvar_analise(con, lid, res)
        novos.append(lid)
    log(f"ciclo: {len(novos)} posts com sinal de compra analisados")

    # Meta do Daniel (mensagens das páginas e comentários no Instagram) – sem pré-filtro de
    # palavras de compra, porque comentário de anúncio é curto ("onde é essa casa?")
    fontes_meta = []
    if (cfg.get("meta") or {}).get("ativo", True):
        from . import coletor_meta
        try:
            itens, fontes_meta = coletor_meta.coletar(cfg)
        except Exception as e:
            itens = []
            log(f"ciclo: Meta do {r['aprovador_nome']} indisponível: {e}")
        for p in itens:
            if db.bloqueado(con, p.get("url", ""), p.get("autor", "")):
                continue
            lid, novo = db.inserir(con, texto=p["texto"], url=p.get("url", ""), autor=p.get("autor", ""),
                                   rede=p["rede"], oferta_id=oferta.get("id"), telefone=S.telefone(p["texto"]))
            if not novo:
                continue
            con.execute("UPDATE leads SET perfil=?, grupo=? WHERE id=?", ("", p.get("grupo", ""), lid))
            con.commit()
            res = cerebro.analisar(cfg, oferta, texto=f"[{p['grupo']}] {p['texto']}", rede=p["rede"],
                                   autor=p.get("autor", ""))
            if res.get("mensagem") and not whatsapp.texto_integro(res["mensagem"]):
                res["mensagem"] = cerebro.mensagem_padrao(cfg, oferta)
            db.salvar_analise(con, lid, res)
            novos.append(lid)
        log(f"ciclo: Meta do {r['aprovador_nome']}: {len(itens)} itens de imóvel ({'; '.join(fontes_meta)})")

    # Só quem vale a pena (vale_a_pena) e ainda não foi relatado nos últimos 7 dias.
    # Os descartados não são enviados para ninguém.
    desde = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    cand = con.execute(
        "SELECT * FROM leads WHERE relatorio_id IS NULL AND recusado_em IS NULL AND COALESCE(analise,'') != '' "
        "AND criado >= ? ORDER BY score DESC", (desde,)).fetchall()
    cand = [c for c in cand if vale_a_pena(c, int(r["nota_minima"]))][:15]
    for c in cand:
        if not (c["mensagem"] or "").strip():
            con.execute("UPDATE leads SET mensagem=? WHERE id=?", (cerebro.mensagem_padrao(cfg, oferta), c["id"]))
    con.commit()
    if fontes_meta:
        buscas = buscas + [f"Meta do {r['aprovador_nome']} ({', '.join(fontes_meta)})"]

    if not cand:
        log("ciclo: nenhum potencial comprador")
        if enviar and r["avisar_quando_vazio"]:
            _avisar(cfg, f"🤖 Danyel: varri o Facebook agora ({'; '.join(buscas)}), li {len(posts)} posts e "
                         f"não achei comprador qualificado para a casa. Sigo procurando.", para_aprovador=False)
        return {"posts": len(posts), "analisados": len(novos), "relatorio": None}

    cur = con.execute("INSERT INTO relatorios (quando, itens) VALUES (?, ?)", (db.agora(), json.dumps([c["id"] for c in cand])))
    rid = cur.lastrowid
    for i, c in enumerate(cand, 1):
        con.execute("UPDATE leads SET relatorio_id=?, numero_relatorio=? WHERE id=?", (rid, i, c["id"]))
    con.commit()
    cand = con.execute("SELECT * FROM leads WHERE relatorio_id=? ORDER BY numero_relatorio", (rid,)).fetchall()
    comentados = comentar_leads(cfg, con, cand) if (enviar and r.get("comentar", True)) else []
    if comentados:
        ids = {c["id"] for c, _ in comentados}
        resto = [c for c in cand if c["id"] not in ids]
        texto = montar_comentados(cfg, comentados, resto)
    else:
        texto = montar_relatorio(cfg, cand, buscas)
    if enviar:
        _avisar(cfg, texto, para_aprovador=True)
        con.execute("UPDATE relatorios SET enviado=1 WHERE id=?", (rid,))
        con.commit()
    log(f"ciclo: relatório #{rid} com {len(cand)} compradores {'enviado' if enviar else '(simulação)'}")
    return {"posts": len(posts), "analisados": len(novos), "relatorio": rid, "texto": texto}


_APROVA = re.compile(r"\baprov\w*\b(.*)", re.I | re.S)
_RECUSA = re.compile(r"^\s*(n[aã]o|recuso|recusa)\b(.*)", re.I | re.S)


def interpretar(texto: str) -> tuple[str, list[int] | str] | None:
    m = _RECUSA.search(texto or "")
    if m:  # "não 2" recusa; "não aprovo" sem número não faz nada
        nums = [int(n) for n in re.findall(r"\d+", m.group(2))]
        return ("recusa", nums) if nums else None
    m = _APROVA.search(texto or "")
    if m:
        resto = m.group(1)
        if re.search(r"\btod[oa]s\b", resto, re.I):
            return ("aprova", "todos")
        nums = [int(n) for n in re.findall(r"\d+", resto)]
        return ("aprova", nums) if nums else None
    return None


def _quando_msg(pre: str) -> datetime | None:
    """'[10:32, 03/11/2026] Daniel: ' -> datetime"""
    m = re.search(r"\[(\d{1,2}):(\d{2}),\s*(\d{1,2})/(\d{1,2})/(\d{4})\]", pre or "")
    if not m:
        return None
    hh, mm, d, mo, a = map(int, m.groups())
    try:
        return datetime(a, mo, d, hh, mm)
    except ValueError:
        return None


def _enviados_hoje(con, canal=None) -> int:
    sql = "SELECT COUNT(*) FROM leads WHERE enviado_em >= ?"
    args = [date.today().isoformat()]
    if canal:
        sql += " AND canal_envio=?"; args.append(canal)
    return con.execute(sql, args).fetchone()[0]


def aprovacoes(cfg=None) -> dict:
    from . import messenger
    cfg = cfg or config.carregar()
    r = _rcfg(cfg)
    if _contato_direto(cfg):
        return {"status": "modo contato direto: o Daniel entra em contato, o robô não envia nada"}
    con = db.conectar()
    rel = con.execute("SELECT * FROM relatorios WHERE enviado=1 ORDER BY id DESC LIMIT 1").fetchone()
    if not rel:
        return {"status": "sem relatório pendente"}

    # Só abre a conversa se a prévia na lista indicar uma resposta (não atrapalha você)
    nome_wa = r.get("aprovador_nome_whatsapp") or r["aprovador_nome"]
    previa = whatsapp.previa(cfg, nome_wa) if r["aprovador_whatsapp"] else ""
    if r["aprovador_whatsapp"] and interpretar(previa):
        msgs = whatsapp.ler_recebidas(cfg, r["aprovador_whatsapp"])
        enviado_em = datetime.fromisoformat(rel["quando"]).replace(second=0)
        for m in msgs:
            q = _quando_msg(m.get("quando", ""))
            if q is None or q < enviado_em:
                continue  # resposta antiga, de antes deste relatório
            ordem = interpretar(m.get("texto", ""))
            if not ordem:
                continue
            acao, nums = ordem
            alvo = con.execute("SELECT * FROM leads WHERE relatorio_id=?", (rel["id"],)).fetchall()
            for l in alvo:
                if nums != "todos" and l["numero_relatorio"] not in nums:
                    continue
                if acao == "aprova" and not l["aprovado_em"] and not l["recusado_em"]:
                    # aprovar alguém abaixo da nota vale: o Daniel decidiu
                    con.execute("UPDATE leads SET aprovado_em=?, etapa=CASE WHEN etapa IN ('novo','descartado') "
                                "THEN 'qualificado' ELSE etapa END WHERE id=?", (db.agora(), l["id"]))
                    db.evento(con, l["id"], f"aprovado por {r['aprovador_nome']} pelo WhatsApp")
                elif acao == "recusa" and not l["enviado_em"] and not l["recusado_em"]:
                    con.execute("UPDATE leads SET recusado_em=?, aprovado_em=NULL WHERE id=?", (db.agora(), l["id"]))
                    db.mudar_etapa(con, l["id"], "descartado")
            con.commit()

    h = datetime.now().hour
    if not (r["horario"][0] <= h < r["horario"][1]):
        return {"status": "fora do horário de envio"}

    fila = con.execute("SELECT * FROM leads WHERE aprovado_em IS NOT NULL AND enviado_em IS NULL AND recusado_em IS NULL "
                       "AND etapa != 'descartado' ORDER BY aprovado_em").fetchall()
    enviados, pendentes, manuais = [], [], []
    for l in fila:
        if _enviados_hoje(con) >= int(r["limite_total_dia"]):
            pendentes.append(l); continue
        canal = _canal(l)
        if canal == "manual":
            con.execute("UPDATE leads SET enviado_em=?, canal_envio='manual' WHERE id=?", (db.agora(), l["id"]))
            db.mudar_etapa(con, l["id"], "abordado")
            manuais.append(l)
            continue
        if canal == "Messenger" and _enviados_hoje(con, "Messenger") >= int(r["limite_facebook_dia"]):
            pendentes.append(l); continue
        if db.bloqueado(con, l["url"], l["autor"]):
            continue
        try:
            if canal == "WhatsApp":
                whatsapp.enviar(cfg, l["telefone"], l["mensagem"])
            elif canal == "Messenger":
                messenger.enviar(cfg, l["perfil"], l["mensagem"])
            else:
                raise RuntimeError("sem telefone nem perfil")
            con.execute("UPDATE leads SET enviado_em=?, canal_envio=?, erro_envio=NULL WHERE id=?", (db.agora(), canal, l["id"]))
            db.mudar_etapa(con, l["id"], "abordado")
            enviados.append((l, canal))
            log(f"enviado lead {l['id']} por {canal}")
        except Exception as e:
            con.execute("UPDATE leads SET erro_envio=? WHERE id=?", (str(e)[:300], l["id"]))
            con.commit()
            log(f"erro ao enviar lead {l['id']}: {e}")
            pendentes.append(l)

    if manuais:
        _avisar(cfg, "👉 *Estes ficam com você* (não há telefone nem perfil para eu mandar sozinho):\n\n" + "\n\n".join(
            f"{l['numero_relatorio']}) {l['autor'] or 'Sem nome'} – {l['grupo'] or l['rede']}\n🔗 {l['url'] or '-'}\n"
            f"✉️ Sugestão de resposta: \"{l['mensagem']}\"" for l in manuais), para_aprovador=True)
    if enviados:
        txt = "✅ *Danyel – mensagens enviadas*\n" + "\n".join(
            f"{l['numero_relatorio']}) {l['autor'] or 'Sem nome'} – por {c}" for l, c in enviados)
        if pendentes:
            txt += f"\n\n⏳ {len(pendentes)} aprovadas ficam para o próximo horário (limite diário de segurança)."
        txt += "\nQuando alguém responder, a conversa chega direto no WhatsApp/Messenger."
        _avisar(cfg, txt, para_aprovador=True)
    return {"enviados": len(enviados), "pendentes": len(pendentes)}


def seguro(func, *a, **k):
    try:
        return func(*a, **k)
    except Exception:
        log("ERRO\n" + traceback.format_exc())
        return None
