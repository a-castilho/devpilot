# Catálogo atual de modelos por provedor

O modal **Modelos de IA → Conectar IA** não usa mais uma lista fixa de modelos.

## Fluxo

1. Ao clicar em **Conectar IA**, o frontend chama `GET /api/providers/model-catalog?refresh=true`.
2. Para cada provedor que já possui uma conexão ativa, o backend descriptografa a credencial somente em memória e consulta a API oficial do provedor.
3. Ao trocar o provedor no modal, o seletor exibe o catálogo correspondente ao provedor selecionado.
4. Em uma primeira conexão, informe a API key e clique em **Atualizar modelos**. O frontend chama `POST /api/providers/discover-models` e a chave não é persistida nessa consulta.
5. Ao salvar a conexão, o backend consulta o provedor novamente. Isso valida a chave e impede persistir identificadores de modelos que já não estejam disponíveis para aquela credencial.
6. Se nenhum modelo for selecionado, todos os modelos atuais devolvidos pelo provedor são associados à conexão.

Sem credencial salva, o DevPilot pode exibir um catálogo público de referência. A disponibilidade efetiva para execução é sempre validada pela conexão salva.

## APIs oficiais consultadas

- OpenAI: `GET https://api.openai.com/v1/models`
- Anthropic: `GET https://api.anthropic.com/v1/models`
- Google Gemini: `GET https://generativelanguage.googleapis.com/v1beta/models`

O provedor `custom` continua manual porque o DevPilot ainda não possui um `base_url` confiável e uma convenção universal de descoberta para APIs arbitrárias.

## Teste real de uma conexão salva

Uma conexão persistida pode executar um handshake mínimo sem devolver a credencial:

```text
POST /api/providers/{connection_id}/test?model={model_id}
```

O teste usa a chave descriptografada somente em memória, pede uma resposta curta e registra na auditoria somente provedor, conexão, modelo e latência.

## AgentOS usando uma conexão salva

O AgentOS continua usando Ollama por padrão. Para escolher explicitamente uma conexão externa já salva em **Modelos de IA**, configure:

```env
DEVPILOT_AGENTOS_MODEL_PROVIDER=google
DEVPILOT_AGENTOS_MODEL_CONNECTION_LABEL=Gemini Principal
DEVPILOT_AGENTOS_MODEL_NAME=gemini-3.6-flash
DEVPILOT_AGENTOS_MODEL_FALLBACK=ollama
DEVPILOT_AGENTOS_MODEL_MAX_OUTPUT_TOKENS=1200
```

`DEVPILOT_AGENTOS_MODEL_PROVIDER` aceita `ollama`, `google`, `openai` ou `anthropic`. O label é opcional; vazio seleciona a conexão ativa mais recente daquele provedor. O modelo pode ser omitido para usar o primeiro modelo salvo na conexão.

O fallback é explícito. Quando configurado como `ollama`, ele só é utilizado para falhas transitórias de rede, rate limit ou erro 5xx. Erros de credencial, modelo ou configuração falham fechados e não trocam silenciosamente de provedor.

A mesma porta de linguagem é usada pelo chat RAG, pelo Council e por etapas `llm` do runtime de grafo. Etapas que escrevem em repositório continuam delegadas ao executor isolado do DevPilot e preservam seus gates de aprovação e segurança.

## Segurança

- API keys nunca retornam pela API do DevPilot.
- A descoberta temporária não persiste a chave.
- Auditoria registra somente provedor, resultado e quantidade de modelos; nunca a credencial.
- Mensagens de erro não repassam o corpo retornado pelo provedor, evitando expor detalhes de conta.
- No Google, a chave é enviada em header, não na URL.
- Conexões salvas continuam criptografadas pelo `Vault`.
- O gateway do AgentOS valida que um modelo explicitamente selecionado pertence à conexão salva antes de abrir a credencial.
- Falhas permanentes de autenticação/configuração não acionam fallback automático.

## Endpoints

```text
GET  /api/providers/model-catalog?refresh=true
POST /api/providers/discover-models
POST /api/providers
POST /api/providers/{connection_id}/test?model={model_id}
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
