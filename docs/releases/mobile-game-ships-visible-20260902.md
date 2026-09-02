# Mobile: Modo Jogo e naves visíveis — 2026-09-02

Correção aplicada sobre a linha 1.2.0 consolidada para garantir no mobile:

- botão **Jogo** visível na navegação inferior;
- acesso direto para `/game/index.html`;
- nave visível em cada card de projeto;
- botão **Jogar** associado ao projeto;
- decoração reaplicada quando os cards são renderizados depois do carregamento do bundle;
- observação de mudanças do DOM para evitar regressão quando Projetos é carregado de forma lazy;
- runtime isolado do jogo com erro visível em vez de tela vazia.

Arquivos principais:

- `app/static/mobile-accordion-menu.js`
- `app/static/mobile-game-ships-stable.js`
- `app/static/game/index.html`
- `app/static/game/runtime.js`
- `app/static/game/game-bootstrap.js`

Teste de contrato: `tests/test_mobile_game_ships_visible_contract.py`.
