# DevPilot Mentor & Security

## Objetivo

O DevPilot passa a operar em quatro funções complementares: analisar, orientar, executar e ensinar. A segurança é uma camada transversal. O princípio de controle permanece o mesmo: análise pode ser automática e somente leitura; qualquer alteração de código, dependência, infraestrutura, push, merge ou deploy continua sujeita às políticas e aprovações existentes.

## System Design

Classificação: **STRUCTURAL**. O recurso altera comportamento de IA, persistência, APIs, autorização, auditoria e interface, mas reutiliza a arquitetura atual: FastAPI, SQLAlchemy, fila persistente, worker/Codex, policy gate, Vault e audit hash-chain.

### Componentes

- `mentor_routes.py`: contratos HTTP, autorização, criação de sessões/tarefas, perfil de aprendizagem e persistência de scans.
- `services/project_context.py`: prepara snapshot limitado e um worktree descartável preso ao commit exato. Exclui arquivos sensíveis, limita quantidade de caminhos/tamanho do arquivo alvo e redige padrões de segredo.
- `services/mentor_executor.py`: executor específico para sessões educacionais; usa worktree descartável, não atualiza `AGENTS.md`, não usa o template comercial de relatório e nunca aciona autocorreção mutável.
- `services/security_scanner.py`: scanner estático local e determinístico no commit exato analisado. Não usa IA e não envia o repositório para terceiros.
- `mentor_models.py`: perfil de competência, eventos educacionais, snapshots, scans e achados.
- `static/mentor-security.js`: interface integrada aos cards de projeto.
- fila/worker existente: continua sendo o único caminho para uma sessão de Mentor que consome IA e para correções/execuções.

### Fluxo do Mentor

1. Usuário escolhe o projeto e o modo.
2. Para `explain`, `teach`, `pair` ou `quiz`, o Context Builder atualiza o clone, resolve o SHA e monta o snapshot em um worktree descartável exatamente nesse commit.
3. O DevPilot cria uma `Task` com marcador `analysis-read-only`; o prompt inclui o SHA/contexto seguro usado na solicitação.
4. O worker identifica `source=mentor` + modo somente leitura e encaminha a tarefa ao `mentor_executor`, não ao executor genérico de análise.
5. O `mentor_executor` abre outro worktree descartável no mesmo SHA, permite inspeção pelo Codex e proíbe qualquer alteração, instalação, commit, push, merge ou deploy.
6. O executor do Mentor não grava `AGENTS.md`, não executa self-healing sobre checkout/credenciais e respeita `DEVPILOT_EXECUTION_ENABLED` e o orçamento de IA.
7. O evento é auditado e registrado em `learning_events`.
8. `learning_skills` guarda somente metadados educacionais úteis; conversas completas não são duplicadas nessa tabela.

`execute` é diferente: não é uma aula somente leitura. Ele cria uma tarefa de desenvolvimento com `requires_approval=true` e `awaiting_approval`, preservando duplication preflight, System Design gate, orçamento e fluxo de execução normal.

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

`POST /api/projects/{project_id}/security/scan` executa uma varredura de baixo custo em um worktree descartável preso ao commit que será registrado no scan. A primeira versão cobre:

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

Regras de execução/configuração não são aplicadas a documentação Markdown/TXT, e regras de CI/CD são limitadas a `.github/workflows`, reduzindo falsos positivos óbvios. Segredos genéricos em diretórios `tests/` e `examples/` também não são classificados automaticamente como credencial de produção.

Cada achado persiste regra, severidade, categoria, arquivo/linha, evidência redigida, impacto e remediação.

### Dependências

O scanner identifica manifests de dependências, mas **não inventa CVEs**. A coluna de cobertura informa `dependency_vulnerability_database=not-enabled` até existir uma fonte de advisories confiável (por exemplo OSV/GitHub Advisory Database) integrada e versionada. Isso evita tratar versão desatualizada como vulnerabilidade comprovada.

### Correção controlada

Consultar a recomendação não altera nada. `POST /security/findings/{finding_id}/fix` com `apply=false` retorna apenas a remediação. Somente `apply=true`, após confirmação na interface, cria uma tarefa `source=security`; a tarefa permanece `awaiting_approval` e passa pelo executor normal. ANALYST/VIEWER não podem iniciar correção.

### Segredos e contexto

O Context Builder não lê arquivos reconhecidos como sensíveis para contexto de IA e redige padrões de senha/token, incluindo Bearer, tokens GitHub e chaves com prefixo `sk-`, no arquivo alvo. O scanner também não retorna o conteúdo de `.env`; nesses casos registra apenas que o arquivo sensível está versionado. Evidências de linhas com possíveis credenciais são redigidas.

O trecho do arquivo alvo não é persistido em `project_snapshots`; o snapshot guarda a identidade/contexto estrutural. A tarefa do Mentor usa contexto redigido e o executor consulta o repositório isolado no SHA correspondente.

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

Quando `DEVPILOT_EXECUTION_ENABLED=false`, uma sessão educacional pode ser registrada, mas o `mentor_executor` não abre repositório nem chama Codex. Isso mantém o mesmo interruptor operacional usado pelo restante do sistema.

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

As tabelas são novas e criadas pelo mecanismo existente `Base.metadata.create_all`; nenhum campo existente é removido ou renomeado. Remover o router/script desativa o recurso sem afetar tarefas já existentes. Scans são append-only; findings antigos continuam vinculados ao commit analisado. Falha ao preparar/fazer fetch do clone retorna erro e não cria scan incompleto.

Sessões somente leitura do Mentor não entram no `AutoRecoveryService`: se houver falha, a sessão encerra sem quarentenar checkout, alternar credenciais ou executar outra reparação mutável. O usuário pode corrigir o ambiente pelo fluxo administrativo normal e executar novamente.

Para produção com evolução contínua do schema, o projeto ainda deve migrar o bootstrap de schema para Alembic, conforme roadmap geral.

## Validação

Mudanças devem passar por:

```bash
pytest
python -m compileall app
```

O CI também valida sintaxe do `mentor-security.js` e presença dos assets Mentor/Security no build estático da Vercel.

Além disso, revisar manualmente o dashboard em desktop/mobile e confirmar:

1. botões Mentor/Segurança em cada projeto;
2. sessões educacionais ficam `queued`, usam o executor dedicado e não alteram `AGENTS.md`;
3. modo Executar fica `awaiting_approval`;
4. scanner e Mentor usam o commit exato registrado no contexto/scan;
5. scan não expõe conteúdo de `.env`;
6. correção só é criada após confirmação e fica `awaiting_approval`;
7. tenant/user isolation dos novos endpoints;
8. execução desabilitada não chama o modelo no Mentor.
