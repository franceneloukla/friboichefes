"""Integração com o bot do WhatsApp (Friboi) — dados do cliente no site.

O bot grava cada cadastro em ``clientes/<documento>.json`` num repositório
**privado**. Este módulo lê esse arquivo no servidor (nunca no navegador) e
mostra na página /meus-dados para o usuário logado.

Instalação:
  1. copie este arquivo para ``server/clientes_portal.py``
  2. no ``server/app.py``, depois de criar ``app``:

        from .clientes_portal import router as clientes_router
        app.include_router(clientes_router)

     (se o import for relativo não funcionar, use ``from clientes_portal import router``)
  3. variáveis de ambiente:
        CLIENTES_REPO=franceneloukla/0000001336     # repositório PRIVADO
        CLIENTES_TOKEN=github_pat_...               # token só-leitura
  4. link no menu: <a href="/meus-dados">Meus dados</a>
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

try:  # reaproveita o template engine e o modelo de usuário do projeto
    from .templates_env import templates
except Exception:  # pragma: no cover
    templates = None  # type: ignore

REPO = os.environ.get("CLIENTES_REPO", "franceneloukla/0000001336")
TOKEN = os.environ.get("CLIENTES_TOKEN", "")
CACHE_SECONDS = 60
_cache: dict[str, tuple[float, dict | None]] = {}

router = APIRouter()

PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meus dados — Friboi Online</title>
<style>
 body{font-family:system-ui,-apple-system,sans-serif;background:#0b1220;color:#e7eefc;margin:0;padding:32px}
 .card{max-width:640px;margin:0 auto;background:#121a2b;border:1px solid #24334d;border-radius:16px;padding:28px}
 h1{font-size:20px;margin:0 0 6px}p{color:#93a4c4;font-size:14px}
 .row{display:flex;justify-content:space-between;gap:16px;padding:10px 0;border-bottom:1px solid #1e2a40;font-size:14px}
 .row span:first-child{color:#93a4c4}.row span:last-child{font-weight:600;text-align:right}
 .erro{color:#fca5a5}
</style></head><body><div class="card">
<h1>Meus dados</h1><p>Cadastro feito no atendimento do WhatsApp.</p>
<div id="dados">__DADOS__</div>
</div></body></html>"""


def _fetch(doc: str) -> dict | None:
    """Lê clientes/<doc>.json do repositório privado (com cache curto)."""
    agora = time.time()
    cache = _cache.get(doc)
    if cache and agora - cache[0] < CACHE_SECONDS:
        return cache[1]

    if not TOKEN:
        raise HTTPException(status_code=503, detail="Integração não configurada")

    url = f"https://api.github.com/repos/{REPO}/contents/clientes/{doc}.json"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github.raw+json",
            "User-Agent": "friboi-site",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            data = None
        else:
            raise HTTPException(status_code=502, detail="Falha ao consultar os cadastros") from err

    _cache[doc] = (agora, data)
    return data


def _linhas(c: dict) -> str:
    pares = [
        ("Nome", c.get("nome")),
        (c.get("tipo_documento") or "Documento", c.get("documento_formatado")),
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
    linhas = "".join(
        f'<div class="row"><span>{k}</span><span>{v}</span></div>' for k, v in pares if v
    )
    return linhas or "<p class='erro'>Cadastro ainda sem dados.</p>"


@router.get("/meus-dados", response_class=HTMLResponse)
def meus_dados(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        return HTMLResponse(PAGE.replace("__DADOS__", "<p class='erro'>Faça login para ver seus dados.</p>"), status_code=401)

    doc = "".join(ch for ch in (getattr(user, "cpf", "") or "") if ch.isdigit())
    if len(doc) not in (11, 14):
        return HTMLResponse(PAGE.replace("__DADOS__", "<p class='erro'>Seu cadastro no site não tem CPF/CNPJ.</p>"))

    cliente = _fetch(doc)
    if not cliente:
        return HTMLResponse(PAGE.replace("__DADOS__", "<p class='erro'>Ainda não encontramos seu cadastro do WhatsApp.</p>"))

    return HTMLResponse(PAGE.replace("__DADOS__", _linhas(cliente)))


@router.get("/api/cliente/meus-dados")
def api_meus_dados(request: Request):
    """Versão JSON, para o front consumir."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="não autenticado")
    doc = "".join(ch for ch in (getattr(user, "cpf", "") or "") if ch.isdigit())
    cliente = _fetch(doc) if len(doc) in (11, 14) else None
    if not cliente:
        raise HTTPException(status_code=404, detail="cadastro não encontrado")
    return cliente
