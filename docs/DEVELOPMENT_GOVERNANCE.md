# Regra de rastreabilidade, revisão e documentação

Esta regra é obrigatória para mudanças funcionais, correções, novas ideias e alterações visuais do projeto.

## Fonte de verdade

- **Issue = intenção:** descreve problema, objetivo, comportamento atual, comportamento esperado e critérios de aceite.
- **PR = execução:** descreve o que foi implementado, arquivos alterados, testes e evidência da interface.
- **Relatório = evidência:** documentos em `docs/issues/` e `docs/reviews/` são gerados automaticamente para auditoria e comparação histórica.

## Regra para cada issue

Toda issue deve registrar contexto/problema, objetivo, estado atual, resultado esperado, critérios de aceite, impacto visual quando existir e riscos/dependências.

O workflow `.github/workflows/issue-documentation.yml` mantém um espelho versionado em `docs/issues/issue-<numero>.md` sempre que a issue é criada, editada, reaberta, fechada ou tem metadados relevantes alterados.

## Novas ideias

Use o template **Nova ideia**. Separe hipótese, valor esperado, experiência/tela esperada, riscos e critérios para decidir se a ideia deve virar implementação.

## Revisão de implementação

Toda Pull Request deve referenciar a issue, explicar o que mudou, indicar como validar, registrar testes e, para UI, incluir evidência antes/depois ou justificar por que não se aplica. Divergências entre solicitado e entregue devem ser registradas antes do merge.

O workflow `.github/workflows/review-documentation.yml` gera `docs/reviews/pr-<numero>.md` com metadados, arquivos alterados, sinais de rastreabilidade e o corpo da PR.

## Comparação planejado x implementado x tela

1. **Planejado:** issue e critérios de aceite.
2. **Implementado:** diff/arquivos e descrição da PR.
3. **Tela/experiência real:** evidência visual, rota, fluxo ou resultado observável.
4. **Divergências:** qualquer diferença deve ser documentada antes do merge.

Para mudanças não visuais, use resposta de API, log, teste, consulta de banco, métrica ou saída reproduzível como evidência.

## Definition of Done

Uma mudança só está pronta quando existe rastreabilidade para issue, critérios foram verificados, testes relevantes foram executados, comportamento observável foi comparado com o esperado, divergências foram registradas e a documentação afetada foi atualizada.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

