# Radar Regula AÍ — tarefa do Super Admin

Este registro acompanha a implementação que faz a entrega histórica do Radar Regula AÍ aparecer no painel `Tarefas ADM` do DevPilot.

## Critérios de validação

- criação idempotente da tarefa histórica;
- ownership pelo `SUPER_ADMIN` do workspace;
- vínculo ao projeto Regula AÍ quando cadastrado;
- evidência de entrega associada ao PR Regula AÍ #79;
- ausência de duplicação em leituras sucessivas do painel;
- isolamento entre Super Admins;
- merge somente após `DevPilot policy` e `DevPilot full quality` aprovados.

Este arquivo também garante um novo head SHA para que o PR de substituição seja validado por um check suite limpo, sem herdar o estado inconsistente dos PRs anteriores.
