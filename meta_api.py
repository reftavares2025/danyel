import re, json, sys, requests
sys.stdout.reconfigure(encoding="utf-8")
TXT = open(r"C:\caminho\para\token_meta.txt", encoding="utf-8-sig").read()
TOKEN = re.search(r"META_ACCESS_TOKEN=(\S+)", TXT).group(1)
V = "https://graph.facebook.com/v21.0/"
def get(p, **kw):
    kw["access_token"] = TOKEN
    r = requests.get(V + p, params=kw, timeout=60); return r.json()
def post(p, files=None, **kw):
    kw["access_token"] = TOKEN
    r = requests.post(V + p, data=kw, files=files, timeout=180); return r.json()
