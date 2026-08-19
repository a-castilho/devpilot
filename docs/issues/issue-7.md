# Issue #7 — Gravador de processos: mouse/teclado + comandos de terminal para sugerir automação

> Documento gerado automaticamente a partir da issue. Edite a issue no GitHub; este arquivo será sincronizado novamente.

## Metadados

- **Status:** Aberta
- **Autor:** @acastilho
- **Responsáveis:** —
- **Labels:** —
- **Milestone:** —
- **Criada em:** 2026-08-19T23:07:07Z
- **Atualizada em:** 2026-08-19T23:07:07Z
- **Fonte:** https://github.com/a-castilho/devpilot/issues/7

## Planejado / descrição da issue

## Ideia
Adicionar ao DevPilot uma sessão curta de aprendizado operacional que observe padrões de interação web e comandos de terminal para identificar tarefas repetitivas candidatas a automação.

## Requisitos
- Botão para gravar por 1 minuto.
- Botão para gravar por 2 minutos.
- Suporte a outras durações sem mudar a arquitetura.
- Coletar cliques de forma aproximada, sem conteúdo da página.
- Coletar padrões de teclado sem armazenar texto digitado.
- Capturar comandos executados no Bash durante uma sessão ativa.
- Sanitizar tokens, senhas e segredos antes de persistir comandos.
- Cruzar eventos web + terminal.
- Detectar comandos, sequências, cliques e atalhos repetidos.
- Produzir score e candidatos à automação.
- Não executar automaticamente a automação nesta primeira etapa; manter revisão humana.

## Critérios de aceite
- Sessão ativa expira automaticamente.
- Somente uma sessão de gravação por workspace.
- Dashboard principal continua capturando eventos enquanto a sessão está ativa.
- Hook Bash não persiste nada quando não há sessão ativa.
- Teste prova que conteúdo digitado não é armazenado.
- Teste prova que segredos comuns do terminal são mascarados.
- Teste prova que fluxo repetido terminal + browser gera candidato híbrido.
- Documentação operacional disponível em `docs/process-learning-recorder.md`.

## Segurança/privacidade
A coleta deve ser explícita, temporizada e mínima. Não implementar keylogger de conteúdo. Não armazenar valores de inputs, texto DOM ou credenciais brutas.

## Regra de revisão

A PR deve referenciar esta issue e comparar **planejado x implementado x resultado observável/tela**. Mudanças visuais exigem evidência antes/depois; mudanças não visuais exigem evidência equivalente.
