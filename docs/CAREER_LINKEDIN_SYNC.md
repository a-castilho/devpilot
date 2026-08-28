# Career / LinkedIn Sync

## Objetivo

O Career Sync transforma um currículo em uma representação canônica do perfil profissional, calcula diferenças em relação ao estado conhecido do LinkedIn, exige aprovação explícita e conecta a conta por OAuth 2.0 oficial.

O currículo continua sendo a fonte de verdade. O módulo não usa Selenium, Playwright, extensão de navegador nem armazena a senha do LinkedIn.

## Arquitetura

```text
DOCX / TXT / Markdown
        |
        v
CV parser
        |
        v
CareerProfile canônico
        |
        +--> headline
        +--> about
        +--> experience[]
        +--> skills[]
        +--> projects[]
        +--> education[]
        +--> languages[]
        |
        v
LinkedIn baseline -> Diff -> Aprovação humana
                           |
                           +--> pacote JSON seguro
                           |
                           +--> publicação oficial (somente quando write capability existir)

LinkedIn OAuth 2.0
        |
        +--> state HMAC + expiração
        +--> authorization code
        +--> token exchange
        +--> OpenID userinfo
        +--> token criptografado no Vault
        +--> LinkedInConnection por workspace/user
```

## Persistência

`career_profiles` mantém o perfil canônico, baseline e snapshot aprovado.

`linkedin_connections` é uma tabela separada para evitar migração destrutiva da tabela existente e contém somente metadados da conexão e credenciais criptografadas:

- `workspace_id` + `user_id` únicos;
- `member_id`, nome e e-mail retornados pelo OIDC;
- `access_token_ciphertext`;
- `refresh_token_ciphertext` quando fornecido;
- scopes e expiração;
- timestamps.

A criptografia reutiliza `app.services.vault.Vault`. Fora de development, `DEVPILOT_ENCRYPTION_KEY` continua obrigatório.

## Endpoints

- `GET /api/career` — perfil, baseline, diff, aprovação e capability da conexão.
- `POST /api/career/cv/import` — upload DOCX/TXT/Markdown.
- `PUT /api/career/linkedin/baseline` — estado conhecido do LinkedIn.
- `POST /api/career/linkedin/approve` — congela a versão revisada.
- `GET /api/career/linkedin/export` — pacote final aprovado.
- `GET /api/career/linkedin/oauth/start` — cria URL OAuth com state assinado.
- `GET /api/career/linkedin/oauth/callback` — valida state, troca code e salva token criptografado.
- `DELETE /api/career/linkedin/oauth` — remove a conexão e as credenciais.
- `POST /api/career/linkedin/publish` — gate de publicação; só prossegue se houver capability oficial de escrita.

## Configuração

```env
DEVPILOT_LINKEDIN_CLIENT_ID=
DEVPILOT_LINKEDIN_CLIENT_SECRET=
DEVPILOT_LINKEDIN_REDIRECT_URI=https://SEU_HOST/api/career/linkedin/oauth/callback
DEVPILOT_LINKEDIN_SCOPES=openid,profile,email
DEVPILOT_LINKEDIN_OAUTH_STATE_TTL_SECONDS=600
```

A redirect URI cadastrada no LinkedIn Developer Portal precisa ser idêntica à configurada no DevPilot. Se `DEVPILOT_LINKEDIN_REDIRECT_URI` estiver vazia, o backend deriva a callback da requisição; em produção recomenda-se uma URL HTTPS fixa.

## Capability de escrita

Conectar por OAuth não implica autorização para editar headline, About, experiências ou outros campos do perfil. Por isso `profile_write` é `false` enquanto o aplicativo não possuir um produto/API e permissões de escrita oficialmente concedidos pelo LinkedIn.

O botão **Sincronizar via API** só é habilitado quando essa capability existir. Até lá o fluxo aprovado continua exportável e auditável. O DevPilot não simula sucesso e não envia o perfil para endpoint não autorizado.

Quando um adapter de escrita aprovado for disponibilizado, ele deverá consumir `approved_profile_json` e preservar o gate atual: diff -> aprovação -> capability -> publicação -> auditoria.

## Auditoria

Eventos existentes:

- `career.cv.imported`;
- `career.linkedin.baseline_updated`;
- `career.linkedin.sync_approved`.

Novos eventos:

- `career.linkedin.oauth_connected`;
- `career.linkedin.oauth_disconnected`;
- `career.linkedin.publish_blocked`.

Tokens e client secret nunca são incluídos no audit log nem enviados para o frontend.

## Segurança

1. currículo limitado a 4 MB;
2. formatos explicitamente permitidos;
3. segregação por usuário/workspace;
4. escrita restrita por role;
5. aprovação explícita e invalidada quando fonte/baseline muda;
6. consistência via SHA-256;
7. OAuth state assinado por HMAC e com TTL;
8. token criptografado pelo Vault;
9. client secret restrito ao backend;
10. nenhuma senha do LinkedIn armazenada;
11. nenhuma automação de navegador;
12. nenhuma alegação de publicação sem capability oficial.

## Arquivos

- `app/career_models.py`
- `app/career_routes.py`
- `app/services/career_sync.py`
- `app/services/linkedin_oauth.py`
- `app/services/vault.py`
- `app/static/career-linkedin.js`
- `tests/test_career_sync.py`
- `tests/test_linkedin_oauth.py`
