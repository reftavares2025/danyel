import re, json, sys, requests
sys.stdout.reconfigure(encoding="utf-8")
TXT = open(r"C:\caminho\para\token_meta.txt", encoding="utf-8-sig", errors="ignore").read()
TOKEN = re.findall(r"EAA[A-Za-z0-9]+", TXT)[-1]
V = "https://graph.facebook.com/v21.0/"
ACT = "act_SEU_ID_DE_CONTA"
def get(p, **kw):
    kw["access_token"] = TOKEN
    return requests.get(V + p, params=kw, timeout=60).json()
def post(p, files=None, **kw):
    kw["access_token"] = TOKEN
    return requests.post(V + p, data=kw, files=files, timeout=180).json()
