# Teste visual no GitHub Actions

O CI do DevPilot executa o teste `tests/test_layout_visual_browser_e2e.py` quando `DEVPILOT_RUN_BROWSER_E2E=1`.

O teste abre o DevPilot em Chromium real e valida:

- layout desktop expandido;
- recolhimento persistente da sidebar;
- ausência de overflow horizontal;
- layout mobile em 390x844;
- controle de recolhimento oculto no mobile;
- métricas em uma coluna no mobile.

As evidências visuais são gravadas em `.artifacts/test-results/visual/` e publicadas pelo job `DevPilot full quality` no artefato `devpilot-test-results-<run>-<attempt>`.

Screenshots gerados:

- `layout-desktop-expanded.png`;
- `layout-desktop-collapsed.png`;
- `layout-mobile-390x844.png`.

Esses screenshots servem como evidência de execução visual do CI. O teste também contém asserções geométricas para falhar automaticamente quando o layout quebra em pontos objetivos.
