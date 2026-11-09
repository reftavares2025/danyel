"""Uso:
  python -m danyel                 abre o painel em http://localhost:5556
  python -m danyel analisar "texto do post"   testa a IA no terminal
  python -m danyel rota            imprime a rota de caça de hoje
  python -m danyel simular         varre o Facebook e mostra o relatório SEM enviar nada
  python -m danyel ciclo           varre, analisa e manda o relatório ao Daniel (cópia ao Régis)
  python -m danyel aprovacoes      lê a resposta do Daniel e envia o que foi aprovado (com travas)
"""
from __future__ import annotations

import json
import sys
import webbrowser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from . import config
    cfg = config.carregar()
    posicionais = [a for a in argv if not a.startswith("--")]
    cmd = posicionais[0] if posicionais else "painel"
    if cmd == "analisar":
        from . import cerebro
        texto = " ".join(posicionais[1:]) or sys.stdin.read()
        print(json.dumps(cerebro.analisar(cfg, config.oferta(cfg, None), texto=texto), ensure_ascii=False, indent=2))
    elif cmd in ("ciclo", "simular"):
        from . import robo
        r = robo.seguro(robo.ciclo, cfg, enviar=(cmd == "ciclo"))
        if r and r.get("texto"):
            print("\n" + r["texto"])
    elif cmd == "aprovacoes":
        from . import robo
        print(robo.seguro(robo.aprovacoes, cfg))
    elif cmd == "rota":
        from . import caca
        for i in caca.rota(cfg):
            print(f"[{i['rede']}] {i['rotulo']}\n   {i['url']}")
    elif cmd == "painel":
        from . import web
        porta = cfg["painel"].get("porta", 5556)
        print(f"Danyel no ar: http://localhost:{porta}  (Ctrl+C para parar)")
        if "--sem-navegador" not in argv:
            webbrowser.open(f"http://localhost:{porta}")
        web.rodar(porta)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
