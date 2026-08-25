# DevPilot Engineering Standard

Padrão obrigatório para prevenir regressões de disponibilidade, travamentos de frontend e confusão de runtime.

## Boot mínimo

O DevPilot usa quatro fases: pré-autenticação, core autenticado, dashboard utilizável e features sob demanda. Antes do login ficam somente os componentes de autenticação/visual. Depois do login, o core automático permanece exatamente em `app.js` e `feature-loader.js`.

Jogo, voz, administração, relatórios, telemetria, Linux e demais módulos opcionais só podem carregar após ação explícita do usuário. É proibida uma segunda onda automática de módulos por timer, idle callback, analytics ou loaders legados.

## Dono único do carregamento

`app/static/feature-loader.js` é o único módulo autorizado a criar tags `<script>` dinamicamente para carregar funcionalidades. Módulos comuns não podem criar loaders escondidos, duplicar assets ou iniciar módulos de domínio ao serem importados.

Novos `MutationObserver` globais em módulos comuns são proibidos. Preferir eventos explícitos como `devpilot:authenticated-core-ready`, `devpilot:dashboard-revealed` e `devpilot:feature-ready`.

## Gate automático

`scripts/check-engineering-standards.py` é obrigatório no CI. Ele valida o boot mínimo, contrato do feature loader, isolamento do login e linhas novas que tentem introduzir loaders ocultos ou MutationObservers fora do carregador oficial.

O gate não deve ser removido para fazer um build passar; a implementação deve ser corrigida.

## CI e main

Uma alteração só é considerada pronta com os gates verdes. A branch `main` deve usar Pull Request e exigir `DevPilot policy` e `DevPilot quality` antes do merge. Mudanças normais de produto não devem entrar por push direto.

## Runtime local

`scripts/devpilot-local-safe.sh` é o caminho padrão para atualização e restart local. O runtime deve identificar porta, PID, commit e health. Uma porta ocupada por processo desconhecido deve interromper a operação em vez de iniciar outra cópia ou mascarar a versão em teste.

## Critério de pronto

Uma mudança está pronta quando política, compileall quando aplicável, sintaxe JavaScript, testes automatizados, validação manual do fluxo visível e CI estiverem aprovados. Regressões importantes devem gerar teste ou gate permanente sempre que tecnicamente viável.
