# Nonblocking AI Recovery Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a esteira continuar com diagnóstico e recovery por IA em segundo plano após falhas não destrutivas, mantendo hard stop somente para risco explícito de integridade/segurança.

**Architecture:** `AutoRecoveryService` decide se a falha ainda exige retry, pode virar continuação degradada ou precisa de hard stop. O worker converte somente decisões não bloqueantes e esgotadas em `self-healing-degraded`, marca a tarefa como concluída para liberar a esteira e cria um recovery interno de baixa prioridade, não recursivo. O hard stop mantém o fluxo de falha/recovery atual.

**Tech Stack:** Python 3.12, FastAPI/SQLAlchemy, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-14-nonblocking-ai-recovery-pipeline-design.md`

## Global Constraints

- Não adicionar novo valor a `TaskStatus`.
- Não ignorar pausa, cancelamento ou bloqueio de orçamento.
- Não expor tokens/segredos em logs ou relatórios.
- Hard stop somente com evidência explícita de risco de perda/corrupção de dados, exposição de segredo/credencial ou operação destrutiva irreversível.
- Recovery em segundo plano nunca exige aprovação e nunca cria recovery recursivo.

---

### Task 1: Contrato de decisão e resultado degradado

**Files:**
- Modify: `tests/test_recovery.py`
- Modify: `app/services/recovery.py`

**Interfaces:**
- Produces: `RecoveryDecision.hard_stop: bool`, `RecoveryDecision.continue_pipeline: bool`, `AutoRecoveryService.should_continue_pipeline(decision) -> bool`, `AutoRecoveryService.degraded_result(decision, original_error, existing_result=None) -> dict`.

- [ ] **Step 1: Write failing tests** para GitHub/auth/repository/database/unknown continuarem, retry/resolved não continuarem, safety integrity bloquear e segredo continuar redigido.
- [ ] **Step 2: Run focused pytest** `pytest -q tests/test_recovery.py` e confirmar falha pelas APIs ainda inexistentes.
- [ ] **Step 3: Implement minimal recovery policy** com detecção `safety_integrity`, flags no `RecoveryDecision`, `should_continue_pipeline` e `degraded_result`.
- [ ] **Step 4: Run focused pytest** e confirmar PASS.
- [ ] **Step 5: Commit** `fix(recovery): allow safe degraded pipeline continuation`.

### Task 2: Recovery por IA não bloqueante

**Files:**
- Modify: `tests/test_failure_recovery_flow_contract.py`
- Modify: `app/services/failure_recovery.py`

**Interfaces:**
- Produces: `ensure_deferred_failure_recovery_task(db, original_task, run, failure, actor='worker') -> Task | None`.

- [ ] **Step 1: Write failing contract tests** exigindo recovery interno `queued`, sem aprovação, prioridade menor e proteção contra recursão.
- [ ] **Step 2: Run focused pytest** `pytest -q tests/test_failure_recovery_flow_contract.py` e confirmar falha.
- [ ] **Step 3: Implement helper** reutilizando `recovery_prompt`, acrescentando marcador de acompanhamento não bloqueante, deduplicação e auditoria `failure_recovery.deferred_created`.
- [ ] **Step 4: Run focused pytest** e confirmar PASS.
- [ ] **Step 5: Commit** `feat(recovery): add deferred AI repair task`.

### Task 3: Worker libera a esteira

**Files:**
- Create: `tests/test_nonblocking_recovery_worker_contract.py`
- Modify: `app/worker.py`

**Interfaces:**
- Consumes: `AutoRecoveryService.should_continue_pipeline`, `AutoRecoveryService.degraded_result`, `ensure_deferred_failure_recovery_task`.
- Produces: execução com `mode=self-healing-degraded`, `degraded=true`, `self_healing.pipeline_continued=true` e `run.status=success` para falha segura esgotada.

- [ ] **Step 1: Write failing worker contract tests** exigindo branch de continuação degradada, criação do recovery deferred e hard stop preservado.
- [ ] **Step 2: Run focused pytest** `pytest -q tests/test_nonblocking_recovery_worker_contract.py` e confirmar falha.
- [ ] **Step 3: Implement worker conversion** logo após a decisão final de recovery, preservando retries e controles existentes.
- [ ] **Step 4: Adapt failure report** para dizer que a etapa ficou degradada, o acompanhamento automático foi criado e a esteira continuará.
- [ ] **Step 5: Run focused tests** `pytest -q tests/test_recovery.py tests/test_failure_recovery_flow_contract.py tests/test_nonblocking_recovery_worker_contract.py`.
- [ ] **Step 6: Commit** `fix(worker): continue pipeline after safe exhausted recovery`.

### Task 4: Verificação integrada e entrega

**Files:**
- Review changed files only.

- [ ] **Step 1: Run compile/tests** `python -m compileall -q app tests` e focused pytest.
- [ ] **Step 2: Open PR against `main`** e usar CI completo do repositório.
- [ ] **Step 3: Inspect failed checks/logs**; corrigir apenas regressões relacionadas.
- [ ] **Step 4: Re-run verification** até os checks relevantes passarem.
- [ ] **Step 5: Review diff** para confirmar que nenhuma alteração de PR #399 foi sobrescrita e que a branch parte do `main` mais recente.
