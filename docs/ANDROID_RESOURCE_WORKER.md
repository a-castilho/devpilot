# Android resource worker

## Classificação

Mudança **STRUCTURAL**: adiciona uma rota de execução auxiliar entre os containers do DevPilot, a fila de host actions, o host Linux e um dispositivo Android/Termux acessado por SSH.

## Objetivo

Reduzir pressão de RAM no notebook sem expor chaves SSH aos containers. O Android executa apenas jobs auxiliares de baixo risco, como `compileall`, `pytest`, `npm test`, `npm run build` e scripts Node explicitamente permitidos.

## Arquitetura

1. O DevPilot grava uma `resource_job` em `runtime/host-actions/pending`.
2. `tools/devpilot_host_action_runner.py` roda no host Linux, valida a ação, o diretório e o allowlist do comando.
3. O runner chama `tools/devpilot_android_worker.sh auto <comando>`.
4. O roteador mede `MemAvailable` do notebook e do Android.
5. Se o notebook estiver abaixo do limite e o Android tiver memória suficiente, o projeto é sincronizado via `rsync` e o comando é executado por SSH.
6. Se o Android estiver offline, sem memória ou falhar, a execução cai para o notebook.

## Contratos e segurança

- As credenciais SSH ficam somente no host Linux; não são montadas no container.
- `.env`, `.env.*`, chaves, segredos, ambientes virtuais, `node_modules`, `data`, `runtime` e logs não são enviados ao Android.
- `.env.example` é preservado para manter documentação/configuração de exemplo.
- `codex`, Docker, `systemctl`, `sudo`, gerenciadores de pacote e comandos privilegiados nunca são roteados automaticamente para o Android.
- O host runner mantém um segundo allowlist, independente do shell router, para impedir que uma payload manipulada execute comando arbitrário.
- O `workdir` continua restrito à raiz `DEVPILOT_DEPLOY_ROOT` já usada pelo host runner.

## Capacidade e limites

Valores padrão:

- notebook: roteamento remoto abaixo de `1200 MB` disponíveis;
- Android: mínimo de `600 MB` disponíveis;
- host SSH: `celular-worker`;
- diretório remoto: `~/projects/<projeto>`.

Podem ser ajustados por:

- `DEVPILOT_REMOTE_THRESHOLD_MB`;
- `DEVPILOT_ANDROID_REMOTE_MIN_MB`;
- `DEVPILOT_ANDROID_WORKER_HOST`;
- `DEVPILOT_ANDROID_REMOTE_ROOT`.

O Codex permanece no notebook. A versão Linux/musl instalada no Termux apresentou timeout de refresh OAuth no ambiente validado, apesar de DNS/TLS funcionarem; por isso `codex` está explicitamente classificado como host-only.

## Falhas e recuperação

- SSH offline: fallback local.
- RAM insuficiente no Android: execução local.
- Falha após seleção remota: fallback local.
- Timeout do host action: código `124` e payload movida para `failed`.
- Comando fora do allowlist: código `64`, sem execução.

## Observabilidade

O resultado de cada host action continua em `runtime/host-actions/processed` ou `runtime/host-actions/failed`. O detalhe registra a rota escolhida (`ANDROID` ou `NOTEBOOK`), memória disponível e saída do job.

## Compatibilidade e deploy

A mudança não altera banco, APIs públicas ou formato existente de `manual_deploy`/`update_local`. `resource_job` é aditiva. O script depende de `ssh` e `rsync` no host e no Termux.

## Rollback

Para desativar sem alterar código, não enfileirar `resource_job`. Para rollback completo, remover `resource_job` de `ALLOWED_HOST_ACTIONS`/`ALLOWED` e remover `tools/devpilot_android_worker.sh`. As ações existentes permanecem independentes.

## Testes

`tests/test_android_resource_worker.py` cobre:

- comandos permitidos;
- rejeição de Codex/Docker/sudo/comandos arbitrários;
- rejeição antes de subprocessos para comando não autorizado;
- geração do payload `resource_job`;
- rejeição de comando vazio.
