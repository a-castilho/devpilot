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

Commits gerados automaticamente apenas em `docs/reviews/**` são documentação derivada e não executam novamente a suíte completa da `main`; qualquer commit que também altere código, configuração, workflow ou outra documentação continua disparando o CI normalmente.

## Continuidade do GitHub Actions

Workflows que executam validação, build, deploy ou comandos do projeto não podem depender obrigatoriamente de minutos de runner hospedado. Eles usam `vars.DEVPILOT_RUNNER || 'ubuntu-latest'`: quando a variável não existe, continuam no runner padrão do GitHub; quando `DEVPILOT_RUNNER` aponta para um runner próprio, o trabalho pesado usa esse runner sem enfraquecer os gates.

Workflows de bookkeeping que apenas consultam a API do GitHub e escrevem metadados não devem competir com `DevPilot policy`/`DevPilot quality` pelo runner próprio escasso. `review-documentation.yml` usa `vars.DEVPILOT_DOCS_RUNNER || 'ubuntu-latest'`; por padrão roda hospedado e pode receber um runner dedicado sem reutilizar implicitamente `DEVPILOT_RUNNER`. Atualizações intermediárias por `synchronize` não geram relatório versionado a cada push; o evento `closed` produz a visão final da PR.

Runner próprio é permitido somente para repositório privado e deve usar uma label dedicada. O caminho padrão de instalação é `bash scripts/setup-github-self-hosted-runner.sh`. O script valida autenticação do `gh`, recusa repositório público, baixa o runner oficial, verifica checksum quando o release fornece digest, registra sem imprimir o token, configura `DEVPILOT_RUNNER` e confirma que o runner ficou online.

Quando os minutos hospedados voltarem a estar disponíveis, remover a variável `DEVPILOT_RUNNER` retorna automaticamente os workflows pesados para `ubuntu-latest`. Nunca remover `DevPilot policy` ou `DevPilot quality` como contorno para falta de minutos.

## Runtime local

`scripts/devpilot-local-safe.sh` é o caminho padrão para atualização e restart local. O runtime deve identificar porta, PID, commit e health. Uma porta ocupada por processo desconhecido deve interromper a operação em vez de iniciar outra cópia ou mascarar a versão em teste.

## Critério de pronto

Uma mudança está pronta quando política, compileall quando aplicável, sintaxe JavaScript, testes automatizados, validação manual do fluxo visível e CI estiverem aprovados. Regressões importantes devem gerar teste ou gate permanente sempre que tecnicamente viável.
