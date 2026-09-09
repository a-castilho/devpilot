# Build Game evidence guard

This branch fixes the false-positive completion path observed in Build Game executions.

- Development Codex runs receive `--sandbox workspace-write`.
- Read-only analysis remains read-only.
- `[Jogo]` / Build Game / Delivery Verifier executions cannot complete successfully without a non-empty `.devpilot/build-game.md` artifact.
- Real Codex errors from stdout are preserved when stderr only contains the benign stdin notice.

The guard is installed centrally from `app.services` and is covered by focused tests in `tests/test_execution_guards.py`.
