# Career / LinkedIn Sync

O Career Sync mantém um perfil canônico derivado do currículo, compara esse perfil com um baseline do LinkedIn e exige aprovação antes de exportar ou tentar qualquer publicação oficial.

## Fluxo

CV -> perfil canônico -> baseline LinkedIn -> diff -> aprovação -> exportação / API oficial quando disponível.

A integração OAuth usa apenas endpoints oficiais do LinkedIn. Não existe automação por Selenium/Playwright, armazenamento de senha do LinkedIn ou simulação de sucesso de publicação.

## Segurança OAuth

- O `state` é assinado por HMAC e possui TTL.
- Cada início de OAuth cria um nonce persistido e de uso único em `linkedin_oauth_states`.
- O nonce é vinculado a um cookie HttpOnly específico da callback; outro navegador não consegue concluir o fluxo iniciado por uma sessão diferente.
- O registro de state é consumido antes da troca do authorization code, impedindo replay.
- Access/refresh tokens são cifrados pelo `Vault` antes da persistência.
- O client secret do aplicativo não fica em claro na configuração: `DEVPILOT_LINKEDIN_CLIENT_SECRET_CIPHERTEXT` deve conter um valor previamente cifrado pelo mesmo Vault/`DEVPILOT_ENCRYPTION_KEY` da instância.

## Configuração

- `DEVPILOT_LINKEDIN_CLIENT_ID`
- `DEVPILOT_LINKEDIN_CLIENT_SECRET_CIPHERTEXT`
- `DEVPILOT_LINKEDIN_REDIRECT_URI`
- `DEVPILOT_LINKEDIN_SCOPES=openid,profile,email`
- `DEVPILOT_LINKEDIN_OAUTH_STATE_TTL_SECONDS=600`

Em produção, configure uma callback HTTPS fixa terminando em `/api/career/linkedin/oauth/callback` e cadastre exatamente a mesma URI no LinkedIn Developer Portal.

## Endpoints

- `GET /api/career`
- `POST /api/career/cv/import`
- `PUT /api/career/linkedin/baseline`
- `POST /api/career/linkedin/approve`
- `GET /api/career/linkedin/export`
- `GET /api/career/linkedin/oauth/start`
- `GET /api/career/linkedin/oauth/callback`
- `DELETE /api/career/linkedin/oauth`
- `POST /api/career/linkedin/publish`

A capability `profile_write` permanece `false` enquanto o aplicativo não possuir produto/permissões de escrita aprovados pelo LinkedIn. O DevPilot não chama endpoints de escrita não autorizados.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**
