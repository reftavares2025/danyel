from m import *
import subprocess, sys
E=json.load(open("estado.json"))
# 1) cria os anúncios que faltam (todos pausados)
subprocess.run([sys.executable, "c6.py"], check=False)
E=json.load(open("estado.json"))
if len(E.get("anuncios",{}))<7:
    print("ainda faltam anúncios:", 7-len(E.get("anuncios",{}))); sys.exit(1)
# 2) com R$10/dia, só 3 anúncios ativos (mais que isso divide verba e ninguém aprende)
ATIVOS=["vA","vC","car"]   # vídeo 'por fora 1 casa', vídeo '1 portão 2 casas', carrossel de 10 fotos
for k,aid in E["anuncios"].items():
    st="ACTIVE" if k in ATIVOS else "PAUSED"
    print(k, st, post(aid, status=st))
print("conjunto:", post(E["conjunto"], status="ACTIVE"))
print("campanha:", post(E["campanha"], status="ACTIVE"))
for k,aid in E["anuncios"].items():
    print(k, get(aid, fields="name,effective_status,status"))
