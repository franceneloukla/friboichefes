"""Acesso do cliente por CPF/CNPJ aos dados do cadastro feito no WhatsApp.

O bot grava ``clientes/<documento>.json`` no repositório do site (JSON cifrado,
AES-256-GCM). Este módulo lê no servidor, decifra e mostra em ``/meus-dados``.

Login: o cliente digita o CPF/CNPJ no site → recebe o cadastro daquele documento.

Variáveis de ambiente:
    CLIENTES_REPO       franceneloukla/friboichefes
    CLIENTES_BRANCH     main
    CLIENTES_KEY        mesma chave configurada no bot
    CLIENTES_PUBLICO    1  (lê raw.githubusercontent, sem token)
    CLIENTES_TOKEN      opcional, só se usar repositório privado
    CLIENTE_SECRET      opcional (default: SECRET_KEY do site)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

try:  # mesma lib do site
    from jose import JWTError, jwt
except Exception:  # pragma: no cover
    jwt = None  # type: ignore

REPO = os.environ.get("CLIENTES_REPO", "franceneloukla/friboichefes")
BRANCH = os.environ.get("CLIENTES_BRANCH", "main")
TOKEN = os.environ.get("CLIENTES_TOKEN", "")
PUBLICO = os.environ.get("CLIENTES_PUBLICO", "1") == "1"
CHAVE = os.environ.get("CLIENTES_KEY", "")
SECRET = os.environ.get("CLIENTE_SECRET") or os.environ.get("SECRET_KEY", "dev-secret-friboi-online")
ALG = "HS256"
COOKIE = "cliente_token"
TTL = 7 * 24 * 3600

router = APIRouter()

_cache: dict[str, tuple[float, dict | None]] = {}


def _norm(doc: str) -> str:
    return re.sub(r"\D", "", doc or "")


def _fmt_doc(doc: str) -> str:
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    if len(doc) == 14:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
    return doc


def _decifrar(payload: dict) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = hashlib.sha256(CHAVE.encode("utf-8")).digest()
    iv = base64.b64decode(payload["iv"])
    tag = base64.b64decode(payload["tag"])
    dados = base64.b64decode(payload["data"])
    return json.loads(AESGCM(key).decrypt(iv, dados + tag, None).decode("utf-8"))


def _fetch(doc: str) -> dict | None:
    agora = time.time()
    cache = _cache.get(doc)
    if cache and agora - cache[0] < 60:
        return cache[1]

    if PUBLICO:
        if not CHAVE:
            raise HTTPException(status_code=503, detail="CLIENTES_KEY não configurada")
        url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/clientes/{doc}.json"
        headers = {"User-Agent": "friboi-site"}
    else:
        if not TOKEN:
            raise HTTPException(status_code=503, detail="Integração não configurada")
        url = f"https://api.github.com/repos/{REPO}/contents/clientes/{doc}.json"
        headers = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github.raw+json", "User-Agent": "friboi-site"}

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            bruto = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            bruto = None
        else:
            raise HTTPException(status_code=502, detail="Falha ao consultar os cadastros") from err

    data = _decifrar(bruto) if bruto and bruto.get("alg") == "A256GCM" else bruto
    _cache[doc] = (agora, data)
    return data


def _token(doc: str) -> str:
    if jwt is None:
        return doc  # fallback (sem lib) — não usar em produção
    exp = datetime.now(timezone.utc) + timedelta(seconds=TTL)
    return jwt.encode({"sub": doc, "kind": "cliente", "exp": int(exp.timestamp())}, SECRET, algorithm=ALG)


def _doc_da_sessao(request: Request) -> str | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    if jwt is None:
        return _norm(token) or None
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALG])
    except JWTError:
        return None
    if payload.get("kind") != "cliente":
        return None
    doc = _norm(payload.get("sub", ""))
    return doc if len(doc) in (11, 14) else None


def _linhas(c: dict) -> str:
    pares = [
        ("Nome", c.get("nome")),
        (c.get("tipo_documento") or "Documento", c.get("documento_formatado") or _fmt_doc(c.get("documento", ""))),
        ("Telefone", c.get("telefone")),
        ("Endereço", " — ".join(x for x in [c.get("endereco"), c.get("bairro")] if x)),
        ("Cidade", c.get("cidade")),
        ("CEP", c.get("cep")),
        ("Estabelecimento", c.get("estabelecimento")),
        ("Banco", c.get("banco")),
        ("Plano", f"R$ {c['plano']} em carnes" if c.get("plano") else None),
        ("Pagamento", c.get("pagamento")),
        ("Desconto correntista", f"{c['desconto_correntista']}% no 1º pedido" if c.get("desconto_correntista") else None),
        ("Situação", "Cadastro ativado" if (c.get("ativacao") or {}).get("pago") else "Aguardando ativação"),
    ]
    return "".join(f'<div class="row"><span>{k}</span><span>{v}</span></div>' for k, v in pares if v)


PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meus dados — Friboi Online</title>
<style>
 body{font-family:system-ui,-apple-system,sans-serif;background:#f5f6f8;color:#212529;margin:0;padding:32px 16px}
 .card{max-width:620px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:28px;box-shadow:0 10px 30px rgba(0,0,0,.06)}
 h1{font-size:22px;margin:0 0 6px}
 p.sub{color:#6b7280;font-size:14px;margin:0 0 20px}
 label{display:block;font-size:13px;color:#374151;margin:14px 0 6px;font-weight:600}
 input{width:100%;padding:12px 14px;border:1px solid #d1d5db;border-radius:10px;font-size:16px;box-sizing:border-box}
 button{width:100%;margin-top:16px;padding:13px;border:0;border-radius:10px;background:#c8102e;color:#fff;font-size:15px;font-weight:700;cursor:pointer}
 .erro{margin-top:14px;color:#b91c1c;font-size:14px}
 .row{display:flex;justify-content:space-between;gap:16px;padding:10px 0;border-bottom:1px solid #eef0f3;font-size:14px}
 .row:last-child{border-bottom:0}
 .row span:first-child{color:#6b7280}
 .row span:last-child{font-weight:600;text-align:right}
 a.sair{display:inline-block;margin-top:18px;font-size:13px;color:#6b7280}
</style></head><body><div class="card">
<h1>Meus dados</h1>
<p class="sub">Entre com o CPF ou CNPJ informado no atendimento do WhatsApp.</p>
__CONTEUDO__
</div></body></html>"""

FORM = """<form method="post" action="/api/cliente/acesso">
  <label for="documento">CPF ou CNPJ</label>
  <input id="documento" name="documento" inputmode="numeric" placeholder="000.000.000-00" required>
  <button type="submit">Entrar</button>
  {erro}
</form>"""


@router.get("/meus-dados", response_class=HTMLResponse)
def meus_dados(request: Request):
    doc = _doc_da_sessao(request)
    if not doc:
        return HTMLResponse(PAGE.replace("__CONTEUDO__", FORM.replace("{erro}", "")))
    cliente = _fetch(doc)
    if not cliente:
        body = FORM.replace("{erro}", '<div class="erro">Não encontramos cadastro para esse CPF/CNPJ.</div>')
        return HTMLResponse(PAGE.replace("__CONTEUDO__", body), status_code=404)
    corpo = "<div>" + _linhas(cliente) + '</div><a class="sair" href="/meus-dados/sair">sair</a>'
    return HTMLResponse(PAGE.replace("__CONTEUDO__", corpo))


@router.get("/meus-dados/sair")
def sair():
    resp = RedirectResponse("/meus-dados", status_code=303)
    resp.delete_cookie(COOKIE, path="/")
    return resp


@router.post("/api/cliente/acesso")
async def acesso(request: Request):
    doc = ""
    tipo = request.headers.get("content-type", "")
    if "application/json" in tipo:
        try:
            doc = _norm((await request.json()).get("documento", ""))
        except Exception:
            doc = ""
    else:
        form = await request.form()
        doc = _norm(str(form.get("documento", "")))

    if len(doc) not in (11, 14):
        body = FORM.replace("{erro}", '<div class="erro">Digite um CPF (11 dígitos) ou CNPJ (14 dígitos).</div>')
        return HTMLResponse(PAGE.replace("__CONTEUDO__", body), status_code=400)

    cliente = _fetch(doc)
    if not cliente:
        body = FORM.replace("{erro}", '<div class="erro">Não encontramos cadastro para esse CPF/CNPJ.</div>')
        return HTMLResponse(PAGE.replace("__CONTEUDO__", body), status_code=404)

    resp = RedirectResponse("/meus-dados", status_code=303)
    resp.set_cookie(COOKIE, _token(doc), max_age=TTL, httponly=True, samesite="lax", path="/")
    return resp


@router.get("/api/cliente/meus-dados")
def api_meus_dados(request: Request):
    doc = _doc_da_sessao(request)
    if not doc:
        raise HTTPException(status_code=401, detail="não autenticado")
    cliente = _fetch(doc)
    if not cliente:
        raise HTTPException(status_code=404, detail="cadastro não encontrado")
    return cliente
