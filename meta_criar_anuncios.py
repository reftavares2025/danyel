from meta_api import *
import time
ACT="act_SEU_ID_DE_CONTA"; PAGE="ID_DA_SUA_PAGINA"
E=json.load(open("meta_estado.json"))
for f,v in E["videos"].items():
    for _ in range(30):
        s=get(v, fields="status").get("status",{}).get("video_status")
        if s=="ready": break
        time.sleep(10)
    print(f, s)
LINK="https://reftavares2025.github.io/casa-cosmopolis/?utm_source=meta&utm_medium=pago&utm_campaign=casa669&utm_content="
FIM=("📍 Jardim Bela Vista III, perto do Centro de Cosmópolis\n"
     "💰 R$ 669 mil – pagamento à vista ou troca com volta em dinheiro\n"
     "🔁 Aceito terreno, chácara, carro ou imóvel de menor valor\n\n"
     "Venda direta com o proprietário. Toque em \"Saiba mais\", veja as fotos e responda 3 perguntas rápidas para agendar a sua visita.")
TXT={
 "A": "Por fora parece 1 casa. Por dentro são 2 casas completas no mesmo terreno de 440 m².\n\n"
      "🏠 Frente: 3 dormitórios, sala, cozinha e banheiro\n🏠 Fundos: 2 dormitórios com suíte, sala, cozinha e copa\n"
      "✅ Água e luz separadas • garagem coberta • churrasqueira\n\n"+FIM,
 "B": "Quem passa na rua não imagina: atrás deste portão tem uma casa de 3 dormitórios e, no fim do corredor, outra casa inteira com 2 dormitórios e suíte.\n\n"
      "Água e luz separadas: more em uma e alugue a outra, ou traga a família para perto, cada um na sua casa.\n\n"+FIM,
 "C": "1 portão. 2 casas. 5 dormitórios. 3 banheiros. Tudo no mesmo terreno de 440 m².\n\n"
      "A casa dos fundos pode virar renda todo mês, porque água e luz já são separadas.\n"
      "✅ Garagem coberta • portão e fechadura eletrônicos • pintura e elétrica novas\n\n"+FIM,
}
TIT={"A":"Por fora 1 casa. Por dentro são 2.","B":"2 casas no mesmo terreno – R$ 669 mil","C":"1 portão, 2 casas – Cosmópolis"}
DESC="Bela Vista III • 440 m² • aceita troca"
def cta(k): return {"type":"LEARN_MORE","value":{"link":LINK+k}}
OPT={"creative_features_spec":{"standard_enhancements":{"enroll_status":"OPT_OUT"}}}
pecas=[
 ("Vídeo A – Por fora 1 casa","vA","video","V2-POR-FORA-1-CASA.mp4","FEED-porfora.png","A"),
 ("Vídeo B – Quem passa na rua","vB","video","V2B-QUEM-PASSA-NA-RUA.mp4","FEED-rua.png","B"),
 ("Vídeo C – 1 portão 2 casas","vC","video","V2C-1-PORTAO-2-CASAS.mp4","FEED-portao.png","C"),
 ("Imagem A – Por fora 1 casa","iA","imagem",None,"FEED-porfora.png","A"),
 ("Imagem B – Quem passa na rua","iB","imagem",None,"FEED-rua.png","B"),
 ("Imagem C – 1 portão 2 casas","iC","imagem",None,"FEED-portao.png","C"),
 ("Carrossel – Tour com 10 fotos","car","carrossel",None,None,"A"),
]
E.setdefault("criativos",{}); E.setdefault("anuncios",{})
for nome,k,tipo,vid,img,t in pecas:
    if k not in E["criativos"]:
        if tipo=="video":
            oss={"page_id":PAGE,"video_data":{"video_id":E["videos"][vid],"image_hash":E["imagens"][img],"message":TXT[t],
                 "title":TIT[t],"link_description":DESC,"call_to_action":cta(k)}}
        elif tipo=="imagem":
            oss={"page_id":PAGE,"link_data":{"image_hash":E["imagens"][img],"link":LINK+k,"message":TXT[t],"name":TIT[t],
                 "description":DESC,"call_to_action":cta(k)}}
        else:
            nomes={"01-arte.png":"2 casas no mesmo terreno","02.jpg":"Garagem coberta","03.jpg":"Casa da frente","04.jpg":"Sala","05.jpg":"Cozinha",
                   "06.jpg":"Dormitórios","07.jpg":"Corredor para os fundos","08.jpg":"Casa dos fundos","09.jpg":"Suíte","10.jpg":"Churrasqueira"}
            filhos=[{"link":LINK+k,"image_hash":h,"name":nomes.get(f,"Ver fotos"),"description":"R$ 669 mil","call_to_action":cta(k)} for f,h in sorted(E["carrossel"].items())]
            oss={"page_id":PAGE,"link_data":{"link":LINK+k,"message":TXT[t],"child_attachments":filhos,"multi_share_optimized":False,
                 "multi_share_end_card":False,"caption":"reftavares2025.github.io"}}
        p=dict(name="CASA COSMÓPOLIS | "+nome, object_story_spec=json.dumps(oss,ensure_ascii=False), degrees_of_freedom_spec=json.dumps(OPT))
        r=post(f"{ACT}/adcreatives",**p)
        if "error" in r and "degrees_of_freedom" in json.dumps(r):
            p.pop("degrees_of_freedom_spec"); r=post(f"{ACT}/adcreatives",**p)
        if "id" not in r: print(nome,"ERRO criativo:",r.get("error",{}).get("error_user_msg") or r); continue
        E["criativos"][k]=r["id"]; json.dump(E,open("meta_estado.json","w"),indent=1)
    if k not in E["anuncios"]:
        r=post(f"{ACT}/ads",name=nome,adset_id=E["conjunto"],status="PAUSED",creative=json.dumps({"creative_id":E["criativos"][k]}))
        if "id" not in r: print(nome,"ERRO anúncio:",r.get("error",{}).get("error_user_msg") or r); continue
        E["anuncios"][k]=r["id"]; json.dump(E,open("meta_estado.json","w"),indent=1)
    print("ok:",nome)
