# Revisão PR #8 — feat: gravador de processos com telemetria web e terminal

> Relatório gerado automaticamente.

## Metadados

- **Estado:** Aberta
- **Autor:** @acastilho
- **Base:** `main`
- **Head:** `feature/telemetry-learning-recorder`
- **Atualizada em:** 2026-08-19T23:07:33Z
- **Fonte:** https://github.com/a-castilho/devpilot/pull/8

## Sinais automáticos de revisão

- **Referência de issue detectada:** SIM
- **Mudança de UI provável:** SIM
- **Evidência visual detectada:** NÃO
- **Arquivos alterados:** 10

> Se houver UI provável sem evidência visual, a revisão deve pedir screenshot/registro ou justificativa explícita.

## Arquivos alterados

- `app/main.py` (+15/-2)
- `app/static/telemetry-capture.js` (+16/-0)
- `app/static/telemetry.css` (+1/-0)
- `app/static/telemetry.html` (+81/-0)
- `app/static/telemetry.js` (+126/-0)
- `app/telemetry.py` (+508/-0)
- `docs/process-learning-recorder.md` (+100/-0)
- `tests/test_telemetry.py` (+75/-0)
- `tools/devpilot_terminal_capture.py` (+71/-0)
- `tools/devpilot_terminal_capture.sh` (+47/-0)

## Descrição e evidências da PR

Closes #7

## Entrega
- sessões temporizadas de 1, 2 e 5 minutos na UI (API aceita 10s–60min)
- captura de cliques em grade aproximada 20x20
- captura de categorias de teclas sem conteúdo digitado
- hook Bash que envia comandos somente com sessão ativa
- sanitização local + backend de tokens, senhas e credenciais comuns
- análise determinística de comandos, sequências, cliques e atalhos repetidos
- candidato híbrido quando há repetição web + terminal
- score de automação e propostas revisáveis
- botão `Gravador de processos` injetado no menu do dashboard
- documentação operacional e testes de privacidade/análise

## Segurança
- não é keylogger de conteúdo
- não armazena valor de inputs nem texto DOM
- nenhum candidato é executado automaticamente nesta etapa
- autenticação reutiliza Bearer token do DevPilot

## Validação esperada
CI deve compilar Python, rodar pytest completo e construir a imagem Docker.

## Comparação obrigatória

1. Issue e critérios de aceite.
2. Diff e arquivos alterados.
3. Resultado observável/tela.
4. Divergências antes do merge.
