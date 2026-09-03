# Bug crítico — botões da UI mobile não respondem

Data: 2026-09-03

## Sintoma
Na tela mobile de Projetos, nenhum botão responde ao toque, incluindo `+ Novo projeto`, ações dos cards e navegação inferior.

## Impacto
Bloqueio total da UI mobile.

## Hipótese inicial
Falha na camada global de eventos/navegação ou overlay interceptando `pointer-events`, não apenas no Project Builder.

## Critérios de aceite
- navegação inferior funciona;
- `+ Novo projeto` abre imediatamente;
- ações dos cards respondem;
- nenhum overlay invisível intercepta cliques;
- teste de regressão cobrindo clique/touch em mobile.
