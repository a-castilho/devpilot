# Correção do gate de engenharia — segunda onda automática no feature-loader

## Problema
O gate `DevPilot policy` rejeita `requestIdleCallback` no `feature-loader.js` porque a política atual proíbe uma segunda onda automática de carregamento após o bootstrap.

A `main` ainda continha um agendamento automático de `projectBuilderEnhancements` após o carregamento de `projectBuilder`, o que fazia qualquer PR falhar no gate antes da suíte de testes.

## Correção
- remove o agendamento automático de `projectBuilderEnhancements` após `projectBuilder`;
- elimina `requestIdleCallback` do `feature-loader.js`;
- mantém o bundle opcional disponível, sem carregamento automático;
- alinha o teste legado do builder ao contrato atual, onde `project-provisioning.js` não pertence ao bundle crítico de `Novo projeto`.

## Escopo
A alteração é propositalmente mínima e independente da PR de correção do GitHub `description`.

## Validação esperada
- `python scripts/check-engineering-standards.py --changed`;
- `node --check app/static/feature-loader.js`;
- `pytest -q tests/test_project_builder_nonblocking_v34.py tests/test_core_action_router.py tests/test_authenticated_minimal_boot.py tests/test_frontend_runtime_circuit_breaker.py`;
- CI `DevPilot policy`.
