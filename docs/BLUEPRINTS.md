# DevPilot Blueprints

## Objetivo

O módulo `app.blueprints` permite armazenar, versionar, selecionar, parametrizar e reutilizar estruturas de projetos já validadas. O DevPilot passa a procurar uma base compatível antes de gerar um projeto do zero e registra no projeto a estratégia `blueprint_delta` quando houver reaproveitamento.

O núcleo foi desenhado para ser portátil. Ele não depende de FastAPI, SQLAlchemy, modelos do DevPilot ou credenciais do DevPilot. A integração HTTP está em `app/blueprint_routes.py`; portanto, o diretório `app/blueprints` pode ser extraído no futuro para pacote ou serviço independente.

## Arquitetura

```text
Requisitos do projeto
        |
        v
Blueprint Matcher
        |
        v
Blueprint Registry ----> versões / métricas de uso
        |
        v
Renderer parametrizado
        |
        v
Projeto base
        |
        v
Geração somente do delta específico
```

### Núcleo portátil

- `domain.py`: entidades do domínio.
- `matcher.py`: ranking determinístico por stack, capabilities, texto, tags e maturidade.
- `renderer.py`: substituição de parâmetros, proteção contra path traversal e verificação de secrets.
- `registry.py`: armazenamento/versionamento persistente em JSON e métricas em JSONL.
- `service.py`: fachada para recomendação, renderização e materialização.
- `defaults.py`: blueprints iniciais distribuídos com o DevPilot.

### Adaptador DevPilot

`app/blueprint_routes.py` expõe o núcleo por HTTP e `app/project_provisioning_routes.py` seleciona automaticamente um blueprint durante o cadastro/provisionamento de projeto.

## Persistência

Por padrão, o registry usa:

```text
data/blueprints/
  <slug>/
    <version>/
      manifest.json
  usage/
    events.jsonl
```

Esse formato não é uma dependência arquitetural. Outro sistema pode implementar outro registry ou evoluir para PostgreSQL/S3 sem alterar matcher, renderer ou domínio.

## Manifesto

Um blueprint possui:

- `slug` e `name`;
- `version`;
- `status`: `experimental`, `candidate`, `stable`, `deprecated`;
- `stack`;
- `capabilities`;
- `parameters`;
- `tags`;
- arquivos parametrizados;
- metadados adicionais.

Exemplo conceitual:

```json
{
  "slug": "saas-fastapi-react",
  "name": "SaaS FastAPI React",
  "version": "1.2.0",
  "status": "stable",
  "stack": {
    "backend": "fastapi",
    "frontend": "react",
    "database": "postgresql"
  },
  "capabilities": ["rest-api", "frontend", "database", "docker"],
  "parameters": ["project_name", "database_name"]
}
```

## Parametrização

O renderer suporta tokens simples:

```text
{{ project_name }}
{{ database_name }}
```

Todos os parâmetros declarados são obrigatórios. O renderer rejeita caminhos absolutos, `..`, colisão de arquivos renderizados e tentativa de sair do diretório de destino.

## Segurança

Blueprints não devem conter secrets reais. O registry executa verificação preventiva para nomes comuns como `token`, `secret`, `password`, `api_key` e chaves privadas.

Valores referenciados por variável de ambiente são permitidos:

```text
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
```

Credenciais continuam sob responsabilidade do cofre/credential manager do sistema consumidor.

## Matching

A pontuação atual considera:

- compatibilidade de stack: 35%;
- capabilities: 30%;
- similaridade textual: 15%;
- tags: 10%;
- maturidade: 10%.

Blueprints `deprecated` não participam da seleção automática. O limiar padrão é `0.35`.

## Integração na criação do projeto

Durante `persist_deferred_project`, o DevPilot:

1. lê `stack`, `capabilities` e `tags` de `codex_config`;
2. respeita `blueprint_slug`/`blueprint_version` quando informados explicitamente;
3. executa o matcher quando não existe seleção explícita;
4. grava a escolha em `codex_config.blueprint`;
5. define `generation_strategy=blueprint_delta` quando encontra base compatível;
6. usa `generation_strategy=from_scratch` quando não encontra;
7. registra evento de uso para métricas.

Falha do mecanismo de blueprint não impede criação do projeto: o sistema faz fallback para o fluxo convencional.

## API

As rotas ficam sob `/api/blueprints`:

- `GET /api/blueprints`: lista blueprints;
- `GET /api/blueprints/{slug}`: obtém versão;
- `POST /api/blueprints`: cadastra/atualiza uma versão (Super Admin);
- `POST /api/blueprints/recommend`: classifica bases para requisitos;
- `POST /api/blueprints/render`: renderiza arquivos sem gravar no filesystem;
- `POST /api/blueprints/usage`: registra resultado/uso;
- `GET /api/blueprints/metrics`: consulta métricas.

## Blueprints iniciais

A instalação inclui:

- `backend-fastapi`;
- `fullstack-fastapi-react`;
- `fullstack-fastapi-react-postgres`.

Eles servem como baseline e podem receber novas versões sem alterar projetos que já guardaram a versão utilizada.

## Uso fora do DevPilot

Outro sistema pode importar somente:

```python
from app.blueprints import BlueprintRegistry, BlueprintService, ProjectRequirements
```

Fluxo mínimo:

```python
registry = BlueprintRegistry("./blueprints")
service = BlueprintService(registry)
matches = service.recommend(ProjectRequirements(stack={"backend": "fastapi"}))
rendered = service.render(matches[0].slug, {"project_name": "MeuProjeto"})
```

No futuro, o diretório pode ser promovido a pacote independente (`devpilot-blueprints` ou nome neutro) sem transportar as rotas, banco ou UI do DevPilot.

## Critérios de aceite implementados

- registry persistente;
- versionamento;
- níveis de maturidade;
- parametrização;
- matcher automático;
- seleção explícita;
- fallback seguro;
- renderização e materialização;
- prevenção de path traversal;
- prevenção básica de secrets;
- métricas de utilização e sucesso;
- integração com criação/provisionamento do DevPilot;
- API administrativa;
- três blueprints iniciais;
- suíte de testes do núcleo.

## Próxima evolução recomendada

O núcleo já suporta reaproveitamento. A evolução natural é conectar a etapa de execução do worker ao `service.materialize()` antes da geração por IA, permitindo que a IA receba o projeto base materializado e produza exclusivamente o delta específico. Depois disso, pode-se adicionar promoção automática de componentes candidatos, sempre exigindo sanitização, testes isolados e política de maturidade antes de virar `stable`.
