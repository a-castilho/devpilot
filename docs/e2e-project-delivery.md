# DevPilot — teste ponta a ponta de criação de projeto

Este fluxo existe para provar, de forma auditável, a criação de um projeto novo desde o repositório vazio até uma entrega em Pull Request draft com CI observável.

## Fluxo implementado

1. Super Admin confirma explicitamente a criação remota.
2. DevPilot cria um repositório privado na organização GitHub configurada, usando `auto_init=true` para garantir uma branch inicial clonável.
3. DevPilot registra `Project` e `Repository` no workspace local.
4. Uma tarefa inicial é colocada na fila para o worker construir um pequeno sistema web Python com health check, testes, README e GitHub Actions CI.
5. O worker executa a tarefa em uma branch isolada e persiste o nome dessa branch na tarefa.
6. Quando a execução termina com sucesso, a tarefa entra em `review`.
7. A publicação remota exige uma segunda confirmação explícita (`confirm_reviewed=true`).
8. DevPilot cria o commit se houver alterações não commitadas, publica somente a branch da tarefa e abre ou reutiliza um Pull Request **draft**.
9. DevPilot consulta status checks e check runs do commit para exibir o estado de CI.
10. Homologação continua como gate humano; merge e deploy permanecem bloqueados até validação explícita.

## API

### Criar projeto e fila inicial

`POST /api/e2e/projects/bootstrap`

Exemplo de payload:

```json
{
  "organization_id": "<organization-id>",
  "name": "Teste Ponta a Ponta",
  "repository_name": "teste-ponta-a-ponta",
  "description": "Projeto descartável para validar o DevPilot",
  "private": true,
  "queue_initial_task": true,
  "confirm_remote_creation": true
}
```

A resposta contém `project_id`, repositório, `task_id` e a matriz inicial de estágios.

### Acompanhar estágios

`GET /api/e2e/projects/{project_id}/status`

O endpoint mostra projeto, repositório, tarefa, execução, Pull Request, CI, próximo passo e os gates de homologação/release.

### Publicar implementação revisada

`POST /api/e2e/tasks/{task_id}/publish`

```json
{
  "confirm_reviewed": true
}
```

Essa ação só funciona quando a tarefa está em `review` e existe um `Run` local bem-sucedido. Ela não faz merge e não faz deploy.

## Critério de aprovação do teste

O caminho automatizado é considerado aprovado até o gate de homologação quando:

- o repositório remoto foi criado;
- o projeto foi registrado;
- a tarefa foi executada com sucesso;
- a branch de tarefa foi persistida;
- a revisão local foi confirmada;
- a branch foi publicada;
- um PR draft foi criado;
- o CI retornou sucesso.

Merge e deploy só devem ser adicionados ao teste depois de validação explícita da homologação e de uma integração de release configurada para o projeto.

## Segurança

- A credencial GitHub permanece no vault e não é devolvida pela API.
- Criação de repositório e publicação exigem confirmação explícita e acesso de Super Admin.
- Repositórios de teste são privados por padrão.
- O fluxo inicial não expõe segredos no projeto gerado.
- Pull Requests são criados como draft.
- Merge e deploy não fazem parte da ação de publicação.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**
