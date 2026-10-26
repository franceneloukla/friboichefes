# Integração com o bot do WhatsApp

O bot de atendimento grava cada cadastro em `clientes/<documento>.json` num
repositório **privado** (hoje `franceneloukla/0000001336`), porque esses arquivos
têm dado pessoal (CPF/CNPJ, endereço, telefone, CEP) e este repositório do site é público.

## O que já está pronto

- `server/clientes_portal.py` — lê o JSON do repositório privado (no servidor) e mostra
  a ficha do cliente na página **/meus-dados** e no endpoint **/api/cliente/meus-dados**.
- O bot grava o arquivo depois que o cliente confirma os dados no WhatsApp.

## Ativar (2 linhas)

Em `server/app.py`, após a criação do `app`:

```python
from .clientes_portal import router as clientes_router
app.include_router(clientes_router)
```

Variáveis de ambiente (Vercel → Settings → Environment Variables):

| Variável | Exemplo |
|---|---|
| `CLIENTES_REPO` | `franceneloukla/0000001336` |
| `CLIENTES_TOKEN` | token fine-grained, **somente leitura** de Contents |

Coloque o link no menu: `<a href="/meus-dados">Meus dados</a>`.

## Formato do arquivo

```json
{
  "documento": "12345678909",
  "tipo_documento": "CPF",
  "documento_formatado": "123.456.789-09",
  "nome": "Carlos Souza",
  "telefone": "5547999998888",
  "cidade": "Joinville",
  "bairro": "Centro",
  "endereco": "Rua das Palmeiras, 120",
  "cep": "89201-000",
  "banco": "Santander",
  "estabelecimento": "Açougue",
  "plano": "1200",
  "pagamento": "30 dias no boleto",
  "desconto_correntista": 7,
  "status": "cadastro_concluido",
  "ativacao": { "pago": false, "valor": "1.00", "txid": "" }
}
```

## Login por CPF/CNPJ

O login atual do site é e-mail + senha, então `/meus-dados` usa o CPF do usuário
logado. Se vocês quiserem "entrar só com CPF", o caminho seguro é confirmar um
código enviado no WhatsApp do cadastro — é o que o portal do bot já faz
(`/portal`, código de 6 dígitos). Sem esse segundo fator, qualquer pessoa que
soubesse um CPF veria nome, endereço e telefone de outra.
