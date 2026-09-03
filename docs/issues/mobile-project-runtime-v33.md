# Falha de sintaxe no runtime mobile de Projetos

Sintoma observado em 2026-09-03: ao entrar em Projetos ou Novo projeto, o navegador registra `SyntaxError: missing ) after argument list` em `mobile-project-card-compact.js` e a navegação parece travar.

A correção V33 remove do runtime mobile o interceptador duplicado de `[data-project-builder-open]` e suas rotinas de builder. Esse arquivo volta a cuidar somente da lista de projetos em modo leve, paginação, nave visual e ação Jogar. A abertura de Novo projeto permanece sob o roteador primário (`viewport-adaptive-v15.js` / `page-navigation-v26.js`).
