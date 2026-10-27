# Integração com o bot do WhatsApp

O bot grava cada cadastro em `clientes/<documento>.json` no repositório
`franceneloukla/friboichefes`. O arquivo é **JSON cifrado** (AES-256-GCM):
quem abre no GitHub vê `{"v":1,"alg":"A256GCM","iv":...,"tag":...,"data":...}`,
e só o site consegue decifrar.

## Ativar

1. `server/clientes_portal.py` já está no repositório.
2. Em `server/app.py`, depois de criar o `app`:

   ```python
   from .clientes_portal import router as clientes_router
   app.include_router(clientes_router)
   ```

3. `requirements.txt`: adicionar `cryptography` (tem wheel para cp314).

4. Variáveis de ambiente no Vercel:

| Variável | Valor |
|---|---|
| `CLIENTES_REPO` | `franceneloukla/friboichefes` |
| `CLIENTES_PUBLICO` | `1` |
| `CLIENTES_KEY` | a mesma chave configurada no bot |
| `CLIENTES_TOKEN` | opcional — só se optarem pelo repositório privado |

5. Link: `<a href="/meus-dados">Meus dados</a>`.

## Login por CPF/CNPJ

- `/meus-dados` mostra o formulário; o cliente digita o CPF (11) ou CNPJ (14) e entra.
- `POST /api/cliente/acesso` valida, busca `clientes/<documento>.json`, decifra e grava o cookie
  `cliente_token` (JWT HS256, 7 dias, httpOnly).
- O botão **Entrar com CPF/CNPJ** também aparece em `/login`.

## Páginas

- `GET /meus-dados` — ficha do usuário logado (nome, CPF, telefone, endereço, CEP,
  banco, plano, pagamento, desconto, situação da ativação)
- `GET /api/cliente/meus-dados` — o mesmo em JSON

## Por que cifrado

O repositório é público. Sem cifra, CPF, endereço e telefone de todos os clientes
ficariam legíveis para qualquer pessoa (e indexáveis). Com a chave só no servidor,
o arquivo continua sendo JSON versionado, mas o dado pessoal não fica exposto.
