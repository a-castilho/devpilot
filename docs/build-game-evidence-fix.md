# Build Game Evidence Gate

Este ajuste impede que uma execução do Build Game seja concluída apenas porque o processo Codex retornou `exit_code = 0`.

Regras implementadas:

- tarefas de desenvolvimento usam `workspace-write`;
- análises read-only permanecem sem permissão de escrita;
- tarefas `[Jogo]`, Build Game e Delivery Verifier exigem `.devpilot/build-game.md` não vazio;
- falhas reais em stdout deixam de ser mascaradas por stderr benigno do Codex;
- quando a autocorreção não resolve, o resultado validado entra no **DevPilot Repair Pipeline**.

A arquitetura completa do fluxo autônomo de incidente, recuperação, PR, CI e reteste está documentada em [`docs/repair-pipeline.md`](repair-pipeline.md).
