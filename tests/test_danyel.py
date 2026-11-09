import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from danyel import caca, cerebro, config, db
from danyel import sinais as S

CFG = config.carregar()


def test_rede_e_telefone():
    assert S.rede_da_url("https://www.facebook.com/groups/1/posts/2") == "Facebook"
    assert S.rede_da_url("https://m.instagram.com/p/x") == "Instagram"
    assert S.rede_da_url("") == "Manual"
    assert S.telefone("me chama (19) 99876-5432 obrigado") == "5519998765432"
    assert S.telefone("+55 19 9 8765 4321") == "5519987654321"
    assert S.telefone("sem telefone 12345") is None


def test_sinais_compra_vs_aluguel():
    c = S.sinais("Procuro casa em Cosmópolis, pago à vista", CFG["caca"]["cidades"])
    a = S.sinais("Procuro casa para alugar em Cosmópolis", CFG["caca"]["cidades"])
    f = S.sinais("Quero comprar casa pelo minha casa minha vida", CFG["caca"]["cidades"])
    assert c["score"] > a["score"] and c["score"] > f["score"]
    assert "financiamento" in f["negativos"]


def test_analise_sem_ia_gera_mensagem():
    cfg = {**CFG, "cerebro": {"ligado": False}}
    r = cerebro.analisar(cfg, config.oferta(cfg, None), texto="Alguém vendendo casa em Cosmópolis? Quero comprar")
    # o Daniel fala direto com a pessoa: sem link de site na mensagem
    assert r["eh_comprador"] and r["mensagem"] and "http" not in r["mensagem"]
    assert "financ" not in r["mensagem"].lower()


def test_comando_claude_isolado():
    cmd = cerebro.comando("claude.exe")
    for flag in ("--safe-mode", "--strict-mcp-config", "--no-session-persistence"):
        assert flag in cmd
    assert cmd[cmd.index("--tools") + 1] == ""


def test_db_dedup_e_lgpd(tmp_path):
    con = db.conectar(tmp_path / "t.db")
    i1, n1 = db.inserir(con, texto="Procuro casa", url="https://facebook.com/p/1", autor="Ana")
    i2, n2 = db.inserir(con, texto="Procuro  casa", url="https://facebook.com/p/1?x=2", autor="Ana")
    assert n1 and not n2 and i1 == i2
    db.salvar_analise(con, i1, {"eh_comprador": True, "score": 80, "intencao": "compra", "mensagem": "oi"})
    assert con.execute("SELECT etapa FROM leads WHERE id=?", (i1,)).fetchone()["etapa"] == "qualificado"
    db.mudar_etapa(con, i1, "abordado")
    assert db.retornos(con, 0)
    db.bloquear(con, i1)
    assert db.bloqueado(con, "", "ana")
    assert con.execute("SELECT texto FROM leads WHERE id=?", (i1,)).fetchone()["texto"] == "[removido a pedido]"


def test_interpretar_aprovacao():
    from danyel.robo import _quando_msg, interpretar
    assert interpretar("APROVO TODOS") == ("aprova", "todos")
    assert interpretar("aprovo 1 e 3") == ("aprova", [1, 3])
    assert interpretar("Aprovado o 2") == ("aprova", [2])
    assert interpretar("NÃO 2") == ("recusa", [2])
    assert interpretar("não aprovo") is None
    assert interpretar("aprovo") is None
    assert interpretar("bom dia") is None
    assert _quando_msg("[10:32, 03/11/2026] Daniel: ").day == 3


def test_relatorio_e_canal(tmp_path):
    from danyel import robo
    con = db.conectar(tmp_path / "r.db")
    lid, _ = db.inserir(con, texto="Quero comprar casa, ligar 19 99713-9070", autor="Maria", telefone="5519997139070")
    db.salvar_analise(con, lid, {"eh_comprador": True, "score": 85, "intencao": "compra", "resumo": "quer comprar", "mensagem": "Oi Maria"})
    con.execute("UPDATE leads SET numero_relatorio=1, grupo='Bazar' WHERE id=?", (lid,))
    l = con.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone()
    assert robo._canal(l) == "WhatsApp"
    # modo padrão: contato direto do Daniel (link do WhatsApp, sem site, sem APROVO)
    t = robo.montar_relatorio(CFG, [l], ["compro casa Cosmópolis"])
    assert "Maria" in t and "nota 85" in t and "https://wa.me/5519997139070" in t and "APROVO" not in t
    # modo antigo continua funcionando
    cfg2 = {**CFG, "robo": {**CFG.get("robo", {}), "modo": "robo_envia"}}
    assert "APROVO TODOS" in robo.montar_relatorio(cfg2, [l], ["compro casa Cosmópolis"])
    assert robo._sem_links("Fotos aqui: https://x.com/a . Você paga à vista?") == "Você paga à vista?"


def test_trava_de_ortografia():
    from danyel.whatsapp import texto_integro
    assert texto_integro("🤖 Teste: acentuação, você, à vista, R$ 669 mil ✅ ção ã õ é ê ç")
    assert not texto_integro("ðŸ¤– Teste do Danyel: se vocÃª estÃ¡ lendo")
    assert not texto_integro("relatÃ³rios")
    assert not texto_integro("texto com �")


def test_rota_tem_links():
    itens = caca.rota(CFG)
    assert len(itens) >= 10 and all(i["url"].startswith("https://") for i in itens)


def test_painel(tmp_path, monkeypatch):
    from danyel import web
    monkeypatch.setattr(web, "CON", db.conectar(tmp_path / "w.db"))
    monkeypatch.setattr(web, "CFG", {**CFG, "cerebro": {"ligado": False}})
    monkeypatch.setattr(web, "analisar_em_segundo_plano", lambda lid: None)
    c = web.app.test_client()
    assert c.get("/").status_code == 200
    assert c.get("/cacar").status_code == 200
    r = c.post("/novo", data={"texto": "Procuro casa em Cosmópolis à vista", "url": "https://facebook.com/x"})
    assert r.status_code == 302
    assert c.get(r.headers["Location"]).status_code == 200
    # outro site não consegue gravar
    assert c.post("/novo", data={"texto": "spam spam spam"}, headers={"Origin": "https://malicioso.com"}).status_code == 403
    assert c.get("/exportar.csv").status_code == 200


def test_so_comenta_em_link_de_post():
    # erro de 04/11: link de busca fez o comentário cair no primeiro post da lista
    from danyel.comentador import eh_link_de_post, texto_comentario
    assert not eh_link_de_post("https://www.facebook.com/search/posts/?q=procuro%20casa")
    assert not eh_link_de_post("https://www.facebook.com/groups/123/")
    assert eh_link_de_post("https://www.facebook.com/groups/123/permalink/456/")
    t = texto_comentario({"texto": "Procuro casa para comprar", "analise": "{}"})
    assert "(19) 90000-0001" in t and "http" not in t
