# DevPilot Mentor & Security

## Objetivo

O DevPilot passa a operar em quatro funções complementares: analisar, orientar, executar e ensinar. A segurança é uma camada transversal. O princípio de controle permanece o mesmo: análise pode ser automática e somente leitura; qualquer alteração de código, dependência, infraestrutura, push, merge ou deploy continua sujeita às políticas e aprovações existentes.

## System Design

Classificação: **STRUCTURAL**. O recurso altera comportamento de IA, persistência, APIs, autorização, auditoria e interface, mas reutiliza a arquitetura atual: FastAPI, SQLAlchemy, fila persistente, worker/Codex, policy gate, Vault e audit hash-chain.

### Componentes

- `mentor_routes.py`: contratos HTTP, autorização, criação de sessões/tarefas, perfil de aprendizagem e persistência de scans.
- `services/project_context.py`: prepara snapshot limitado por commit. Exclui arquivos sensíveis, limita quantidade de caminhos e tamanho do arquivo alvo e redige linhas com aparência de segredo.
- `services/security_scanner.py`: scanner estático local e determinístico. Não usa IA e não envia o repositório para terceiros.
- `mentor_models.py`: perfil de competência, eventos educacionais, snapshots, scans e achados.
- `static/mentor-security.js`: interface integrada aos cards de projeto.
- fila/worker existente: continua sendo o único caminho para uma sessão de Mentor que consome IA e para correções/execuções.

### Fluxo do Mentor

1. Usuário escolhe o projeto e o modo.
2. Para `explain`, `teach`, `pair` ou `quiz`, o Context Builder atualiza o clone, resolve o commit e gera/reutiliza um snapshot seguro.
3. O DevPilot cria uma `Task` com marcador `analysis-read-only`; o worker a executa em worktree descartável.
4. O prompt informa nível e competência do usuário e proíbe alterações.
5. O evento é auditado e registrado em `learning_events`.
6. `learning_skills` guarda somente metadados educacionais úteis; conversas completas não são duplicadas nessa tabela.

`execute` é diferente: não é uma aula somente leitura. Ele cria uma tarefa de desenvolvimento com `requires_approval=true` e `awaiting_approval`, preservando duplication preflight e System Design gate.

### Modos

- `explain`: explicação curta baseada em evidência do projeto.
- `teach`: aula em etapas, exemplo e checagem de entendimento.
- `pair`: orientação passo a passo sem editar arquivos.
- `quiz`: três perguntas progressivas baseadas no projeto.
- `execute`: tarefa de implementação, sempre aguardando aprovação explícita.

### Perfil educacional

Níveis permitidos por competência: `beginner`, `intermediate`, `advanced`, `expert`. O nível é escopado por usuário + projeto + competência. O usuário pode corrigi-lo explicitamente. Campos auxiliares registram conceitos vistos, pontos para revisão e confiança.

## Segurança

### Scanner local

`POST /api/projects/{project_id}/security/scan` executa uma varredura de baixo custo no clone Git. A primeira versão cobre:

- arquivos sensíveis versionados (`.env`, chaves e certificados privados);
- possíveis segredos hard-coded;
- `subprocess(..., shell=True)` e `os.system`;
- `eval`/`exec`;
- CORS com wildcard;
- debug habilitado no código;
- validação de assinatura JWT desabilitada;
- GitHub Actions com `permissions: write-all`;
- `pull_request_target` como ponto de revisão de risco;
- Dockerfile sem `USER` não-root.

Cada achado persiste regra, severidade, categoria, arquivo/linha, evidência redigida, impacto e remediação.

### Dependências

O scanner identifica manifests de dependências, mas **não inventa CVEs**. A coluna de cobertura informa `dependency_vulnerability_database=not-enabled` até existir uma fonte de advisories confiável (por exemplo OSV/GitHub Advisory Database) integrada e versionada. Isso evita tratar versão desatualizada como vulnerabilidade comprovada.

### Correção controlada

Consultar a recomendação não altera nada. `POST /security/findings/{finding_id}/fix` com `apply=false` retorna apenas a remediação. Somente `apply=true`, após confirmação na interface, cria uma tarefa `source=security`; a tarefa permanece `awaiting_approval` e passa pelo executor normal. ANALYST/VIEWER não podem iniciar correção.

### Segredos e contexto

O Context Builder não lê arquivos reconhecidos como sensíveis para contexto de IA e redige padrões de token/senha no arquivo alvo. O scanner também não retorna o conteúdo de `.env`; nesses casos registra apenas que o arquivo sensível está versionado. Evidências de linhas com possíveis credenciais são redigidas.

## APIs

### Mentor

`POST /api/projects/{project_id}/mentor`

```json
{
  "mode": "teach",
  "question": "Me ensine como funciona o RBAC deste projeto",
  "target": "app/security.py",
  "skill": "RBAC",
  "level": "intermediate"
}
```

`GET /api/projects/{project_id}/mentor/skills`

`PUT /api/projects/{project_id}/mentor/skills/{skill}`

### Segurança

`POST /api/projects/{project_id}/security/scan`

`GET /api/projects/{project_id}/security/scans`

`GET /api/projects/{project_id}/security/findings?status=open`

`POST /api/projects/{project_id}/security/findings/{finding_id}/fix`

```json
{"apply": true, "extra_instruction": "Preserve compatibilidade com Python 3.12"}
```

## Custos e capacidade

A parte local (snapshot e scanner) não usa tokens de IA. O snapshot é cacheado por `project_id + commit_sha + context_hash`; o Context Builder limita a 220 caminhos e 12 mil caracteres para o arquivo alvo. Uma sessão do Mentor é uma tarefa normal e, portanto, usa a fila e os mecanismos de orçamento existentes. O modo `execute` não recebe tratamento privilegiado e continua sob policy/approval.

## Autorização

- VIEWER: consulta scans/achados/skills, sem iniciar consumo de IA, scan ou correção.
- ANALYST: pode usar modos educacionais e iniciar scan; não pode iniciar `execute` nem correção.
- ADMIN/OWNER/SUPER_ADMIN: podem usar todos os modos; execução/correção continuam aguardando aprovação.
- O escopo de todas as consultas inclui `workspace_id` e `project_id`; skills também incluem `user_id`.

## Auditoria

Eventos adicionados:

- `mentor.requested`
- `mentor.skill_updated`
- `security.scan_completed`
- `security.fix_requested`

Não são registrados conteúdos secretos em `details`.

## Falhas, rollback e compatibilidade

As tabelas são novas e criadas pelo mecanismo existente `Base.metadata.create_all`; nenhum campo existente é removido ou renomeado. Remover o router/script desativa o recurso sem afetar tarefas já existentes. Scans são append-only; findings antigos continuam vinculados ao commit analisado. Falha ao preparar/fazer fetch do clone retorna erro 502 e não cria scan incompleto.

Para produção com evolução contínua do schema, o projeto ainda deve migrar o bootstrap de schema para Alembic, conforme roadmap geral.

## Validação

Mudanças devem passar por:

```bash
pytest
python -m compileall app
```

Além disso, revisar manualmente o dashboard em desktop/mobile e confirmar:

1. botões Mentor/Segurança em cada projeto;
2. sessões educacionais ficam `queued` e somente leitura;
3. modo Executar fica `awaiting_approval`;
4. scan não expõe conteúdo de `.env`;
5. correção só é criada após confirmação e fica `awaiting_approval`;
6. tenant/user isolation dos novos endpoints.
