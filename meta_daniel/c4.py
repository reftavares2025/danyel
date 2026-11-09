from m import *
import os, time

D = r"C:\caminho\para\criativos"
estado = json.load(open("estado.json")) if os.path.exists("estado.json") else {}
img = estado.setdefault("imagens", {})
for f in ["FEED-porfora.png","FEED-rua.png","FEED-portao.png","STORY-porfora.png","STORY-rua.png","STORY-portao.png"]:
    if f in img: continue
    with open(os.path.join(D, f), "rb") as fh:
        r = post(f"{ACT}/adimages", files={f: fh})
    h = list(r.get("images", {}).values())
    img[f] = h[0]["hash"] if h else None
    print(f, "->", "ok" if img[f] else r)
car = estado.setdefault("carrossel", {})
C = r"C:\caminho\para\criativos\PUBLICAR\3-INSTAGRAM e FACEBOOK (perfil e pagina)\CARROSSEL (postar nesta ordem)"
for f in sorted(os.listdir(C)):
    if f in car: continue
    with open(os.path.join(C, f), "rb") as fh:
        r = post(f"{ACT}/adimages", files={f: fh})
    h = list(r.get("images", {}).values()); car[f] = h[0]["hash"] if h else None
    print("carrossel", f, "->", "ok" if car[f] else r)
vid = estado.setdefault("videos", {})
for f in ["V2-POR-FORA-1-CASA.mp4","V2B-QUEM-PASSA-NA-RUA.mp4","V2C-1-PORTAO-2-CASAS.mp4"]:
    if f in vid: continue
    with open(os.path.join(D, f), "rb") as fh:
        r = requests.post(f"https://graph-video.facebook.com/v21.0/{ACT}/advideos", data={"access_token": TOKEN, "name": f}, files={"source": fh}, timeout=600).json()
    vid[f] = r.get("id"); print(f, "->", "ok" if vid[f] else r)
json.dump(estado, open("estado.json","w"), indent=1)
