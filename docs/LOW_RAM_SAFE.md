# Otimização de RAM segura no Linux

O DevPilot adota a regra **medir → testar temporariamente → validar → aplicar → permitir rollback**. O objetivo é reduzir consumo de memória sem sacrificar rede, DNS, áudio, Docker, DevPilot ou sessões do usuário.

## Ferramenta

Use:

```bash
bash scripts/low-ram-safe.sh audit
```

O comando acima não altera o sistema. Ele registra memória, swap, processos de maior RSS, candidatos conhecidos e verificações de saúde.

Para testar todos os candidatos, um por vez, sempre restaurando o serviço ao final:

```bash
bash scripts/low-ram-safe.sh test-all
```

Para testar apenas um serviço:

```bash
bash scripts/low-ram-safe.sh test cups.service
```

O teste temporário mede a RAM antes/depois, valida rede, DNS, Docker, DevPilot em `127.0.0.1:8080` quando estiver escutando e o servidor de áudio. O serviço é reiniciado mesmo se o teste for interrompido.

## Serviços candidatos

A lista inicial é deliberadamente conservadora:

- `cups.service`
- `cups-browsed.service`
- `bluetooth.service`
- `ModemManager.service`
- `avahi-daemon.service`
- `whoopsie.service`

Um candidato não deve ser desativado apenas porque consome memória. Primeiro confirme que a funcionalidade correspondente não é necessária naquela máquina.

## Serviços protegidos

A ferramenta bloqueia alterações nestes serviços:

- `NetworkManager.service`
- `dbus.service`
- `systemd-logind.service`
- `systemd-resolved.service`
- `docker.service`
- `containerd.service`
- `ssh.service`

Esses serviços não entram na otimização automática porque o risco de quebrar conectividade, sessão, resolução, containers ou acesso remoto é maior que o benefício esperado.

## Aplicação persistente

Somente depois de um teste aprovado e de confirmar que a função do serviço não será usada:

```bash
bash scripts/low-ram-safe.sh apply cups.service --confirm
```

Se qualquer verificação crítica falhar, o script tenta reverter imediatamente.

## Rollback

```bash
bash scripts/low-ram-safe.sh rollback cups.service
```

## Relatórios

Auditorias são gravadas em:

```text
~/.local/state/devpilot/low-ram/
```

Isso permite comparar medições ao longo do tempo sem alterar o estado do sistema durante a fase de diagnóstico.

## Critério de decisão

Considere aplicar uma desativação apenas quando todos estes pontos forem verdadeiros:

1. O serviço não é utilizado pela máquina ou pelo usuário.
2. O teste temporário não causa regressão funcional.
3. O ganho de memória é relevante em relação ao total disponível.
4. Existe rollback conhecido e testado.
5. Rede, DNS, áudio, Docker e DevPilot continuam operacionais.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

