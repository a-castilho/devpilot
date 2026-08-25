# Boot de frontend em máquinas de pouca memória

O DevPilot mantém a tela de autenticação deliberadamente leve. Antes do login, somente `auth-ui.js` executa o fluxo de sessão. `app.js` e o dashboard só entram depois que `/api/auth/me` valida a sessão armazenada.

Depois de uma sessão válida, somente o núcleo da interface é carregado imediatamente. Os módulos opcionais não são mais inicializados em massa após o login:

- recursos de **Projetos**, **Tarefas**, **Modelos**, **Relatórios**, **Auditoria** e **Organizações** entram quando a respectiva visão é aberta;
- **jogo**, **voz** e **exemplos** entram somente após uma ação explícita do usuário;
- **Linux**, módulos administrativos secundários e captura de telemetria aguardam a primeira interação real e uma janela adicional antes de iniciar;
- a rota `/mobile` carrega apenas o shell móvel necessário e aplica `frontend-performance.css`, que remove efeitos de composição caros como `backdrop-filter`, filtros de SVG e animações não essenciais.

O `task-analytics.js` não pode iniciar assets do jogo. Os scripts legados de jogo (`system-tests.js`, subfases, sessões, bônus de URL e armas) pertencem ao grupo explícito `game` do bootstrap autenticado.

Cada grupo é carregado em série, com `requestIdleCallback`, oportunidade de pintura entre módulos e intervalos curtos. O objetivo é evitar picos de compilação JavaScript, registros simultâneos de `MutationObserver`, rajadas de requisições e pressão de GPU/compositor em máquinas com pouca RAM.

A regra é de desempenho, não de autorização: todos os endpoints continuam protegidos pelo backend. O carregamento sob demanda apenas evita trabalho de UI que ainda não é necessário.
