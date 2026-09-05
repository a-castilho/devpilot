# Issue #332 — docs(governance): registrar regra geral de trabalho do DevPilot

> Documento gerado automaticamente a partir da issue. Edite a issue no GitHub; este arquivo será sincronizado novamente.

## Metadados

- **Status:** Aberta
- **Autor:** @acastilho
- **Responsáveis:** —
- **Labels:** —
- **Milestone:** —
- **Criada em:** 2026-09-05T13:07:00Z
- **Atualizada em:** 2026-09-05T13:07:00Z
- **Fonte:** https://github.com/a-castilho/devpilot/issues/332

## Planejado / descrição da issue

## Contexto / problema
As regras gerais e permanentes de trabalho do DevPilot precisam existir como documentação global, separada dos `AGENTS.md` específicos de cada projeto.

## Objetivo
Criar uma fonte versionada e explícita para a regra geral de trabalho aplicável a qualquer projeto, repositório, linguagem, framework, banco, servidor, ambiente ou infraestrutura operada pelo DevPilot.

## Estado atual
O repositório possui `AGENTS.md` com regras específicas do próprio DevPilot e documentação de governança em `docs/`, mas a regra geral fornecida pelo usuário ainda não está registrada como documento global separado.

## Resultado esperado
Adicionar `docs/REGRA_GERAL_TRABALHO.md` contendo a regra geral completa, sem misturar detalhes específicos de projetos.

## Critérios de aceite
- Documento global separado de `AGENTS.md`.
- Conteúdo preserva os princípios, prioridades, regras de segurança, Git, banco, testes, deploy, documentação e validação fornecidos pelo usuário.
- Nenhum secret ou informação específica de projeto é introduzido.
- Alteração isolada e facilmente reversível.

## Impacto visual
Não se aplica.

## Riscos / dependências
Baixo risco. Mudança exclusivamente documental. Não altera runtime, banco, infraestrutura ou configuração.

## Regra de revisão

A PR deve referenciar esta issue e comparar **planejado x implementado x resultado observável/tela**. Mudanças visuais exigem evidência antes/depois; mudanças não visuais exigem evidência equivalente.
