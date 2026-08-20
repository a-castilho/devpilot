#!/usr/bin/env python3
"""Aplica correção idempotente de toque/mobile ao RepetAI local.

A correção é deliberadamente injetada no <head> do frontend existente para
preservar a UI e a persistência atuais. Ela:
- bloqueia mousemove sintético gerado por toque (evita touch => mousemove + click);
- usa Pointer Events para reconhecer a origem touch/pen sem armazenar conteúdo;
- agenda a análise automaticamente quando o botão Analisar estiver disponível;
- compacta tabelas no mobile sem rolagem horizontal desnecessária.

Use REPETAI_HOME para apontar outro diretório em testes/operação.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

MARKER = "REPETAI_MOBILE_INPUT_FIX_V2"

INJECTION = r"""
<!-- REPETAI_MOBILE_INPUT_FIX_V2 -->
<style id="repeatai-mobile-input-fix-v2">
@media (max-width: 640px) {
  html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
  body { overflow-x: hidden; }
  table {
    width: 100% !important;
    min-width: 0 !important;
    table-layout: fixed !important;
  }
  th, td {
    padding: 8px 5px !important;
    font-size: 13px !important;
    line-height: 1.28 !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
  }
  th:nth-child(1), td:nth-child(1) { width: 13%; }
  th:nth-child(2), td:nth-child(2) { width: 23%; }
  th:nth-child(3), td:nth-child(3) { width: 28%; }
  th:nth-child(4), td:nth-child(4),
  th:nth-child(5), td:nth-child(5) { width: 18%; }
  .table-wrap, .table-responsive, [class*="table-wrap"],
  [class*="table-responsive"] {
    max-width: 100% !important;
    overflow-x: clip !important;
  }
}
</style>
<script id="repeatai-mobile-input-fix-v2-script">
(() => {
  if (window.__REPETAI_MOBILE_INPUT_FIX_V2__) return;
  window.__REPETAI_MOBILE_INPUT_FIX_V2__ = true;

  let lastTouchLikeAt = -Infinity;
  let autoAnalyzeTimer = 0;
  let autoAnalyzeClick = false;
  let autoAnalyzeRetries = 0;

  const markTouchLike = event => {
    if (event.pointerType === 'touch' || event.pointerType === 'pen') {
      lastTouchLikeAt = performance.now();
    }
  };

  // Pointer Events são a fonte canônica para saber se a interação veio de
  // dedo/caneta. Não gravamos texto nem conteúdo do usuário aqui.
  window.addEventListener('pointerdown', markTouchLike, true);
  window.addEventListener('pointermove', markTouchLike, true);
  window.addEventListener('pointerup', markTouchLike, true);
  window.addEventListener('pointercancel', markTouchLike, true);

  // Fallback para navegadores antigos/embeds que não exponham pointerType.
  window.addEventListener('touchstart', () => {
    lastTouchLikeAt = performance.now();
  }, {capture: true, passive: true});
  window.addEventListener('touchmove', () => {
    lastTouchLikeAt = performance.now();
  }, {capture: true, passive: true});
  window.addEventListener('touchend', () => {
    lastTouchLikeAt = performance.now();
  }, {capture: true, passive: true});

  // Chromium/Android pode emitir mousemove sintético imediatamente antes do
  // click de um toque. Bloqueamos apenas esse mousemove; o click continua
  // chegando ao RepetAI como uma única ação lógica.
  window.addEventListener('mousemove', event => {
    const fromTouchCapabilities =
      event.sourceCapabilities &&
      event.sourceCapabilities.firesTouchEvents === true;
    const nearTouch = performance.now() - lastTouchLikeAt < 900;

    if (fromTouchCapabilities || nearTouch) {
      event.stopImmediatePropagation();
      event.stopPropagation();
    }
  }, true);

  const findAnalyzeButton = () =>
    [...document.querySelectorAll('button')].find(button =>
      /(^|\s)analis(ar|e|ar agora)(\s|$)/i.test(
        (button.textContent || '').trim()
      )
    );

  const runAutoAnalyze = () => {
    autoAnalyzeTimer = 0;
    const button = findAnalyzeButton();

    if (!button || button.disabled) {
      if (autoAnalyzeRetries < 4) {
        autoAnalyzeRetries += 1;
        autoAnalyzeTimer = window.setTimeout(runAutoAnalyze, 600);
      }
      return;
    }

    if (autoAnalyzeClick || /analisando/i.test(button.textContent || '')) {
      return;
    }

    autoAnalyzeRetries = 0;
    autoAnalyzeClick = true;
    try {
      button.click();
    } finally {
      queueMicrotask(() => {
        autoAnalyzeClick = false;
      });
    }
  };

  const scheduleAutoAnalyze = event => {
    if (autoAnalyzeClick) return;

    // Ignora o próprio botão de análise para não criar um loop.
    if (
      event &&
      event.type === 'click' &&
      event.target &&
      /analis/i.test((event.target.textContent || '').trim())
    ) {
      autoAnalyzeRetries = 0;
      clearTimeout(autoAnalyzeTimer);
      return;
    }

    autoAnalyzeRetries = 0;
    clearTimeout(autoAnalyzeTimer);
    autoAnalyzeTimer = window.setTimeout(runAutoAnalyze, 1200);
  };

  // Cada nova interação apenas rearma o debounce. Ao encerrar a captura, o
  // botão Analisar fica disponível e é acionado uma única vez. Se o stop for
  // assíncrono, fazemos até quatro tentativas curtas sem observar/mutar a UI.
  ['click', 'pointerup', 'scroll', 'keydown'].forEach(type => {
    window.addEventListener(
      type,
      scheduleAutoAnalyze,
      type === 'scroll'
        ? {capture: true, passive: true}
        : true
    );
  });
})();
</script>
""".strip()


def candidate_score(path: Path, text: str) -> int:
    score = 0
    lowered = text.lower()

    if "padrões detectados" in lowered or "padroes detectados" in lowered:
        score += 8
    if "eventos recentes" in lowered or "últimos eventos" in lowered:
        score += 6
    if "mousemove" in lowered:
        score += 5
    if "repeatai" in lowered:
        score += 4
    if path.name.lower() == "index.html":
        score += 3
    if "analisar" in lowered:
        score += 2

    return score


def find_target(root: Path) -> tuple[Path | None, str | None]:
    candidates: list[tuple[int, Path, str]] = []

    for path in root.rglob("*.html"):
        try:
            if len(path.relative_to(root).parts) > 5:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue

        score = candidate_score(path, text)
        if score:
            candidates.append((score, path, text))

    if not candidates:
        return None, None

    candidates.sort(key=lambda row: (row[0], -len(row[1].parts)), reverse=True)
    _, path, text = candidates[0]
    return path, text


def inject(text: str) -> str:
    if MARKER in text:
        return text

    head_close = text.lower().find("</head>")
    if head_close >= 0:
        return text[:head_close] + INJECTION + "\n" + text[head_close:]

    body_open = text.lower().find("<body")
    if body_open >= 0:
        return text[:body_open] + INJECTION + "\n" + text[body_open:]

    return INJECTION + "\n" + text


def main() -> int:
    root = Path(
        os.environ.get(
            "REPETAI_HOME",
            str(Path.home() / "Documents" / "repeatai"),
        )
    ).expanduser()

    if not root.is_dir():
        print(f"REPETAI_MOBILE_FIX=SKIP projeto não encontrado: {root}")
        return 0

    target, text = find_target(root)

    if target is None or text is None:
        print(
            "REPETAI_MOBILE_FIX=WARNING "
            "frontend HTML do RepetAI não identificado"
        )
        return 0

    if MARKER in text:
        print(f"REPETAI_MOBILE_FIX=OK já aplicado: {target}")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f"{target.name}.backup-{stamp}")
    shutil.copy2(target, backup)

    updated = inject(text)
    target.write_text(updated, encoding="utf-8")

    if MARKER not in target.read_text(encoding="utf-8"):
        shutil.copy2(backup, target)
        print("REPETAI_MOBILE_FIX=ERROR validação do patch falhou")
        return 1

    print(f"REPETAI_MOBILE_FIX=OK arquivo: {target}")
    print(f"REPETAI_MOBILE_FIX=BACKUP {backup}")
    print(
        "REPETAI_MOBILE_FIX=CHANGES "
        "touch-dedupe,pointer-origin,auto-analysis,responsive-table"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
