# Dashboard operacional do usuário — contagens confiáveis

## Preflight de duplicidade

O dashboard já existe na `main`. Esta entrega não recria a tela: corrige a inconsistência entre totais globais e as 20 tarefas recentes usadas no navegador, acrescenta estado de sincronização e cobre o comportamento com testes.

## Classificação

STRUCTURAL, porque amplia o contrato interno de `GET /api/overview`. A alteração é aditiva e retrocompatível.

## Arquitetura afetada

- `app/api.py`: agrega tarefas por status no banco, sempre dentro do workspace/escopo já aplicado pela sessão.
- `app/static/app.js`: usa os totais autoritativos e mantém fallback para backends anteriores.
- `app/static/index.html` e `styles.css`: apresentam sincronização, falha e acessibilidade.
- testes: validam contrato, semântica dos status e estrutura visual.

## Contrato

`GET /api/overview` preserva os campos existentes e adiciona:

- `status_counts`: mapa completo dos valores de `TaskStatus`;
- `attention`: totais de aprovações, falhas/bloqueios e itens ativos.

Nenhum campo existente é removido ou renomeado.

## Dados, segurança e isolamento

Não há migração. As consultas usam `Task.workspace_id == ws.id`; os filtros globais de conta existentes continuam ativos. Nenhum prompt, segredo ou credencial é retornado.

## Falhas e recuperação

O navegador conserva os últimos dados válidos quando uma atualização falha e muda o indicador para estado degradado. O botão permite nova tentativa explícita. O fallback local mantém compatibilidade durante atualização parcial do ambiente.

## Desempenho e escalabilidade

Uma única agregação `GROUP BY status` substitui a inferência incorreta baseada na página recente. O payload acrescentado é constante e pequeno, limitado ao enum de status.

## Observabilidade

O indicador inferior informa sucesso, horário da última atualização ou falha. Não é criado polling automático, preservando o boot progressivo e o limite de RAM.

## Deploy, compatibilidade e rollback

Backend e frontend podem ser publicados juntos ou separadamente. Frontend novo aceita backend antigo; backend novo mantém clientes antigos. Rollback consiste em reverter os commits desta branch.

## Testes

- contagens completas por status e totais derivados;
- isolamento entre workspaces/contas;
- uso do contrato autoritativo no front-end;
- estado visual de sincronização e controle acessível;
- gates de engenharia e matriz crítica.

## Riscos e trade-offs

A agregação adiciona uma consulta leve por atualização manual. Em troca, elimina divergências e evita transportar todas as tarefas ao navegador.
