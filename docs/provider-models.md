# Catálogo atual de modelos por provedor

O modal **Modelos de IA → Conectar IA** não usa mais uma lista fixa de modelos.

## Fluxo

1. Ao clicar em **Conectar IA**, o frontend chama `GET /api/providers/model-catalog?refresh=true`.
2. Para cada provedor que já possui uma conexão ativa, o backend descriptografa a credencial somente em memória e consulta a API oficial do provedor.
3. Ao trocar o provedor no modal, o seletor exibe o catálogo correspondente ao provedor selecionado.
4. Em uma primeira conexão, informe a API key e clique em **Atualizar modelos**. O frontend chama `POST /api/providers/discover-models` e a chave não é persistida nessa consulta.
5. Ao salvar a conexão, o backend consulta o provedor novamente. Isso valida a chave e impede persistir identificadores de modelos que já não estejam disponíveis para aquela credencial.
6. Se nenhum modelo for selecionado, todos os modelos atuais devolvidos pelo provedor são associados à conexão.

## APIs oficiais consultadas

- OpenAI: `GET https://api.openai.com/v1/models`
- Anthropic: `GET https://api.anthropic.com/v1/models`
- Google Gemini: `GET https://generativelanguage.googleapis.com/v1beta/models`

O provedor `custom` continua manual porque o DevPilot ainda não possui um `base_url` confiável e uma convenção universal de descoberta para APIs arbitrárias.

## Segurança

- API keys nunca retornam pela API do DevPilot.
- A descoberta temporária não persiste a chave.
- Auditoria registra somente provedor, resultado e quantidade de modelos; nunca a credencial.
- Mensagens de erro não repassam o corpo retornado pelo provedor, evitando expor detalhes de conta.
- No Google, a chave é enviada em header, não na URL.
- Conexões salvas continuam criptografadas pelo `Vault`.

## Endpoints

```text
GET  /api/providers/model-catalog?refresh=true
POST /api/providers/discover-models
POST /api/providers
```

Exemplo da descoberta temporária:

```json
{
  "provider": "anthropic",
  "api_key": "<secret>"
}
```

Resposta:

```json
{
  "provider": "anthropic",
  "source": "live",
  "models": [
    {"id": "<model-id>", "label": "<display-name>"}
  ],
  "refreshed_at": "<timestamp>"
}
```

A lista efetiva depende da API key e do que o provedor disponibiliza para aquela conta no momento da consulta.
