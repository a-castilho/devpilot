# Nonblocking AI Recovery Pipeline

## Objetivo

Falhas de execução não devem interromper a esteira quando ainda for seguro continuar. O DevPilot deve primeiro esgotar autocorreções determinísticas, registrar o diagnóstico, criar uma missão de recuperação por IA em segundo plano quando a causa permanecer aberta e liberar as etapas independentes seguintes. O ser humano é a última instância.

## Regra de decisão

O fluxo passa a ser: executar -> diagnosticar -> tentar correções/retries -> classificar risco -> continuar de forma degradada ou aplicar hard stop.

`hard_stop` só é permitido quando o erro contém evidência explícita de que continuar pode causar perda/corrupção de dados, exposição de segredo/credencial ou operação destrutiva irreversível. Falhas de GitHub, rede, autenticação de ferramenta, permissão de filesystem, indisponibilidade de serviço/banco e erros desconhecidos devem ser informados e convertidos em continuação degradada depois das tentativas automáticas seguras.

## Resultado degradado

Uma continuação degradada é um resultado terminal da tentativa atual com `exit_code=0`, `mode=self-healing-degraded`, `degraded=true` e `self_healing.status=deferred`. Ela não afirma que o trabalho técnico foi concluído; informa que a etapa não pôde ser concluída integralmente, registra causa/evidências, marca `pipeline_continued=true` e permite que a esteira avance.

O relatório ao cliente deve dizer explicitamente que a etapa ficou degradada/adiante, que a causa continua registrada e que o DevPilot abriu acompanhamento automático. Não deve instruir o usuário a reenfileirar a tarefa nem apresentar autorização como pré-condição para continuar.

## Recuperação por IA em segundo plano

Ao produzir uma continuação degradada, o worker cria uma única tarefa interna `failure-recovery` de baixa prioridade, sem aprovação humana. Essa missão reutiliza o diagnóstico e o objetivo original, procura uma solução segura, executa testes quando possível e registra evidências. A tarefa é interna e não vira fase do jogo. Se a recuperação falhar, não cria recovery recursivo. Se tiver sucesso, não reabre uma tarefa original já concluída de forma degradada; a correção beneficia as etapas seguintes e permanece auditável.

## Hard stop

O hard stop preserva `exit_code != 0`, não converte a tarefa em sucesso e mantém o mecanismo de recovery existente. A decisão deve carregar `hard_stop=true` e uma estratégia de proteção de integridade. O relatório deve explicar o risco concreto que impede continuação automática.

## Compatibilidade

Não adicionar novo valor ao enum `TaskStatus`; o estado degradado fica nos logs/resultado da execução, evitando migração e impacto em consumidores existentes. O worker continua usando `completed` para uma etapa liberada com degradação e `failed/blocked` apenas para hard stop ou controles explícitos como orçamento/pausa/cancelamento.

## Testes obrigatórios

- GitHub 401/403 após retries permite continuação degradada.
- `codex_auth`, `filesystem_permission`, `database`, `repository_state` e `unknown` permitem continuação degradada quando não há risco explícito.
- retry/resolved não são convertidos prematuramente em degradado.
- mensagem de corrupção/integridade gera hard stop.
- segredos continuam redigidos nos relatórios.
- worker converte falha não bloqueante em resultado degradado e cria recovery interno de baixa prioridade.
- recovery interno não cria recovery recursivo e não reabre a tarefa original degradada.
