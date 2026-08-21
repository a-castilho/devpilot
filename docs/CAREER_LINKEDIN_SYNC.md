# Career / LinkedIn Sync

## Objetivo

O Career Sync transforma um currículo em uma representação canônica de perfil profissional, calcula diferenças em relação ao estado conhecido do LinkedIn e exige aprovação explícita antes de gerar um pacote de sincronização.

O currículo é a fonte de verdade. O módulo não usa Selenium, Playwright, extensões de navegador ou automação de interface do LinkedIn.

## Fluxo atual

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
LinkedIn baseline
        |
        v
Diff
        |
        v
Aprovação humana
        |
        v
Pacote JSON aprovado
```

## Integração com o DevPilot

- autenticação e roles existentes;
- persistência por `workspace_id` e `user_id` na tabela `career_profiles`;
- auditoria com `career.cv.imported`, `career.linkedin.baseline_updated` e `career.linkedin.sync_approved`;
- nova opção `Career / LinkedIn` na interface;
- aprovação invalidada quando currículo ou baseline muda;
- SHA-256 do currículo para impedir aprovação de uma versão diferente da revisada.

## Endpoints

- `GET /api/career` — perfil, baseline, diff e status.
- `POST /api/career/cv/import` — upload DOCX/TXT/Markdown.
- `PUT /api/career/linkedin/baseline` — estado conhecido do LinkedIn.
- `POST /api/career/linkedin/approve` — congela a versão revisada.
- `GET /api/career/linkedin/export` — pacote final aprovado.

O parser DOCX usa apenas biblioteca padrão (`zipfile` + XML), sem dependência adicional.

## Publicação automática

O modo operacional atual é `approval_and_export`. A API de perfil do LinkedIn e as APIs de edição de perfil exigem acesso aprovado pelo LinkedIn. Quando esse acesso existir, um adapter oficial poderá consumir o mesmo `approved_profile_json`, sem refazer parser, diff, aprovação, auditoria ou UI.

A automação via navegador permanece intencionalmente desativada.

## Arquivos

- `app/career_models.py`
- `app/career_routes.py`
- `app/services/career_sync.py`
- `app/static/career-linkedin.js`
- `tests/test_career_sync.py`

## Segurança

1. currículo limitado a 4 MB;
2. formatos explicitamente permitidos;
3. segregação por usuário/workspace;
4. escrita restrita por role;
5. aprovação explícita;
6. consistência via SHA-256;
7. eventos auditáveis;
8. sem automação de navegador;
9. sem token do LinkedIn armazenado nesta fase.
