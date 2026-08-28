# DevPilot no GitHub Codespaces

Este modo existe para desenvolver pelo celular sem manter o computador local ligado.

## Abrir

No GitHub, abra o repositório `a-castilho/devpilot`, toque em **Code** → **Codespaces** → **Create codespace on main**.

O Codespace instala automaticamente Python 3.12 e as dependências de teste do DevPilot. O ambiente usa SQLite por padrão, portanto não precisa iniciar Docker nem PostgreSQL.

## Iniciar o DevPilot

```bash
bash scripts/codespaces-start.sh
```

A porta `8080` será encaminhada pelo Codespaces. Abra a URL indicada na aba **Ports**.

## Worker

Só inicie o worker quando precisar executar tarefas em fila:

```bash
python -m app.worker
```

Para manter o consumo baixo, deixe `DEVPILOT_EXECUTION_ENABLED=false` enquanto estiver apenas desenvolvendo ou testando a interface/API.

## Segredos

Não grave chaves reais no repositório. Para OpenAI ou outros provedores, use **Codespaces secrets** do GitHub ou configure as variáveis somente na sessão.

## Encerrar

Quando terminar, pare o Codespace pelo GitHub. Isso interrompe o consumo da franquia de Codespaces; o código continua salvo no GitHub.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

