# DevPilot — Blueprints de Projetos

## Objetivo

O DevPilot deve reutilizar estruturas de engenharia já validadas antes de gerar um projeto do zero. O fluxo passa a ser **entender → investigar → planejar → procurar blueprint/componentes → compor → gerar somente o delta → validar → revisar → documentar → entregar → aprender**.

## Conceitos

- **Blueprint**: arquitetura reutilizável e versionada de um projeto.
- **Component**: capacidade reutilizável (auth, postgres, worker, deploy etc.).
- **Manifest**: metadados, stack, capacidades, parâmetros, arquivos e validações.
- **Matcher**: ranqueia blueprints pela compatibilidade com requisitos.
- **Composer**: materializa um blueprint e componentes sem sobrescrever arquivos por acidente.
- **Usage tracking**: registra uso, sucesso/falha e score para evolução posterior.

## Segurança

Blueprints não podem conter tokens, senhas, cookies, `.env` reais ou chaves privadas. O registry rejeita padrões de secrets antes de persistir ou materializar um blueprint. Credenciais continuam no Vault/ProviderCredential.

## Versionamento e maturidade

Versões são imutáveis e seguem `MAJOR.MINOR.PATCH`. Estados: `experimental`, `candidate`, `stable`, `deprecated`. Projetos existentes permanecem associados à versão utilizada; uma versão nova não altera projetos já gerados.

## Matching

O score considera stack, capacidades, tipo, maturidade e histórico de validação. O matcher prefere `stable`, mas nunca elimina a validação do projeto gerado. Se nenhum candidato alcançar o threshold, o fluxo convencional continua disponível.

## API

- `GET /api/blueprints`: lista versões registradas.
- `POST /api/blueprints`: registra uma versão imutável (super admin).
- `POST /api/blueprints/match`: ranqueia candidatos para uma especificação.
- `POST /api/blueprints/materialize`: gera arquivos em diretório permitido (super admin).
- `POST /api/blueprints/{name}/{version}/outcome`: registra resultado de validação.

## Manifest mínimo

```json
{
  "name": "fullstack-fastapi-react-postgres",
  "version": "1.0.0",
  "type": "fullstack",
  "status": "stable",
  "stack": {"backend": "fastapi", "frontend": "react", "database": "postgresql"},
  "capabilities": ["rest-api", "docker", "health-check"],
  "parameters": ["project_name", "repository_name"],
  "files": {"README.md": "# {{ project_name }}\n"},
  "validation": ["backend_tests", "frontend_tests"]
}
```

## Regras operacionais

1. Antes de criar arquitetura nova, consultar o registry.
2. Reutilizar somente versões compatíveis e validadas.
3. Gerar apenas o delta específico do projeto.
4. Nunca sobrescrever arquivos existentes sem autorização explícita.
5. Todo código reutilizado passa pelos mesmos testes do código novo.
6. Melhorias de um projeto não viram padrão global automaticamente; primeiro devem ser sanitizadas, testadas isoladamente e promovidas.

## Evolução

A primeira implementação entrega registry, versionamento, parametrização segura, matcher determinístico, materialização, métricas e API. A fase de aprendizado pode posteriormente propor novos componentes/versões com base em projetos concluídos, mantendo promoção controlada e auditável.
