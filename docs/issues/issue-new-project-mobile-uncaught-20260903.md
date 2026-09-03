# Novo projeto mobile: Uncaught durante carregamento de organizations

Em 2026-09-03, ao clicar em **Novo projeto** na view Projetos, o console do navegador registrou `Uncaught` em `mobile-project-card-compact.js` próximo da sincronização do seletor de organizações. A aba Network mostrou request `organizations` durante a abertura.

## Critério
- abrir `new-project` sem aguardar organizations;
- nenhuma exceção da sincronização de organizações pode impedir a view;
- sincronização de `<select>` deve evitar dependência do construtor global `Option`;
- carregamento de organizations deve ser postergado e isolado, sem bloquear interação;
- falha de organizations mantém `Sem organização` e não derruba demais botões.
