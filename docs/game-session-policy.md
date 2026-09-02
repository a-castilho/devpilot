# Regra de sessão do Modo Jogo

## Regra obrigatória

O Modo Jogo é um boundary de sessão do DevPilot.

1. Entrar no Modo Jogo exige uma sessão autenticada válida.
2. Enquanto o Modo Jogo estiver ativo, qualquer saída dele encerra a sessão autenticada atual.
3. A saída remove `devpilot-token`, limpa `sessionStorage` e usa `window.location.replace('/')`.
4. Não existe navegação `Modo Jogo -> dashboard` preservando a mesma sessão.
5. Depois de sair do Modo Jogo, qualquer acesso ao DevPilot deve passar novamente pelo fluxo de login.
6. O histórico do navegador não pode restaurar uma tela autenticada anterior ao logout.
7. O runtime do jogo nunca deve ser reutilizado depois da saída; a próxima autenticação inicia um novo boot do frontend.

## Motivo

Essa política elimina a classe de falhas causada por reentrada em um runtime de jogo que já foi movido entre views, observado por `MutationObserver` ou carregado por bundles lazy. Em vez de tentar recuperar DOM/listeners/estado de uma sessão anterior, a saída estabelece um boundary determinístico: logout e novo boot autenticado.

## Implementação

`app/static/game-shell.js` mantém uma guarda idempotente `logoutInProgress`. Quando `exitGame()` detecta que o modo jogo estava ativo, ele emite `devpilot:game:exited` e executa o logout forçado. O botão de saída e uma navegação que remova a view ativa convergem para o mesmo `exitGame()`.

## Regressão

`tests/test_game_shell_frontend.py` deve falhar se a saída voltar a usar `showView('overview')`, se deixar de remover `devpilot-token` ou se deixar de substituir a URL atual pelo shell de login.
