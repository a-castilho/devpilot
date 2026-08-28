# System Design no DevPilot

O DevPilot aplica System Design como gate obrigatório antes da implementação de tarefas de desenvolvimento.

## Fluxo

Demanda → preflight de duplicidade → System Design → implementação → testes → revisão → deploy/rollback.

## Classificação

### SIMPLE

Mudança local e de baixo impacto que não altera arquitetura, contratos, persistência, autenticação/autorização, integrações, infraestrutura, IA, multi-tenancy, processamento assíncrono, filas, concorrência, topologia de deploy ou APIs consumidas externamente.

Antes de editar arquivos, o executor deve registrar `System Design dispensado` e justificar a dispensa.

### STRUCTURAL

Mudança que afeta um ou mais dos seguintes pontos:

- arquitetura ou responsabilidade de componentes;
- API ou contratos externos/internos;
- modelo de dados ou migrações;
- autenticação, autorização ou isolamento de tenant;
- integrações externas;
- filas, concorrência ou processamento assíncrono;
- infraestrutura, cloud ou topologia de deploy;
- comportamento de IA;
- escalabilidade, capacidade ou desempenho estrutural;
- observabilidade, recuperação de falhas ou compatibilidade.

Antes da implementação, o executor deve registrar um System Design conciso cobrindo arquitetura afetada, componentes, contratos, dados, segurança, dependências, falhas e recuperação, escalabilidade, observabilidade, deploy, compatibilidade, rollback, testes, riscos e trade-offs.

## Regra de execução

Nenhuma edição deve começar antes da conclusão do preflight de duplicidade e do System Design, ou da dispensa justificada para mudança SIMPLE.

A regra também é incluída no `AGENTS.md` gerado pelo DevPilot para que os projetos analisados herdem o mesmo padrão de engenharia.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

