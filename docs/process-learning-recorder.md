# Gravador de Processos — DevPilot

## Objetivo

O Gravador de Processos cria janelas curtas de observação para detectar trabalho repetitivo e transformar evidência real de uso em candidatos de automação.

A sessão combina três fontes:

1. cliques no dashboard/web app;
2. padrões de teclado sem armazenar o texto digitado;
3. comandos executados em terminais Bash com o hook local ativado.

O primeiro estágio **não executa automações sozinho**. Ele calcula padrões, score de automação e propostas que podem virar script, alias, tarefa DevPilot ou workflow híbrido após revisão humana.

## Interface

Abra:

```text
http://127.0.0.1:8080/telemetry
```

A tela oferece exatamente os botões de 1 minuto e 2 minutos. A API continua preparada para sessões entre 10 segundos e 60 minutos caso outras durações sejam adicionadas no futuro.

Durante a gravação, a sessão continua ativa no backend mesmo ao voltar para o dashboard principal. O dashboard recebe um capturador leve que consulta a sessão ativa e envia somente os eventos permitidos.

## Ativar captura de terminal

A captura de terminal é **opt-in**. No repositório DevPilot, habilite-a explicitamente com um token de acesso válido para as rotas normais autenticadas de telemetria:

```bash
export DEVPILOT_URL=http://127.0.0.1:8080
export DEVPILOT_TERMINAL_CAPTURE=1
export DEVPILOT_TELEMETRY_TOKEN='seu-token-de-acesso'
source "$HOME/Documents/devpilot/tools/devpilot_terminal_capture.sh"
```

`DEVPILOT_BOOTSTRAP_TOKEN` não deve ser usado para telemetria. O hook é instalado apenas no shell Bash em que o arquivo foi carregado. Para tornar permanente, essas variáveis podem ser adicionadas ao ambiente de inicialização escolhido pelo operador, mantendo o token fora do Git.

Se a API responder 401 ou 403, o helper abre um circuit breaker persistente para a impressão digital do token atual. Invocações seguintes não criam novas requisições com a mesma credencial inválida. A troca do token constitui recuperação e permite novas tentativas sem persistir o segredo em disco.

Sem sessão ativa, o servidor responde que nada foi capturado e nenhum evento é persistido.

## Privacidade

### Teclado

O navegador não envia caracteres digitados. São enviados apenas grupos como:

- texto;
- navegação;
- edição;
- modificador;
- tecla de função;
- atalho.

Atalhos com `Ctrl`, `Alt` ou `Meta` podem guardar a combinação curta, por exemplo `ctrl+c`, porque isso ajuda a identificar uma etapa operacional sem armazenar conteúdo de campos.

### Mouse

As coordenadas são reduzidas para uma grade 20x20. Não são armazenados texto do elemento, conteúdo da página, valores de formulário ou seletores completos do DOM.

### Terminal

A sanitização ocorre duas vezes: no helper local e novamente no backend. São mascarados padrões comuns de:

- Bearer token;
- `--password`, `--token`, `--api-key`, `--secret`;
- variáveis de ambiente com nomes de token/senha/segredo;
- tokens GitHub conhecidos;
- chaves com prefixo `sk-`;
- credenciais embutidas em URL HTTP(S).

O caminho de trabalho troca `/home/<usuario>` por `~` antes de persistir.

## API

- `POST /api/telemetry/sessions`
- `GET /api/telemetry/sessions/active`
- `GET /api/telemetry/sessions`
- `GET /api/telemetry/sessions/{id}`
- `POST /api/telemetry/sessions/{id}/events`
- `POST /api/telemetry/terminal/command`
- `POST /api/telemetry/sessions/{id}/stop`
- `POST /api/telemetry/sessions/{id}/analyze`

Todas as rotas usam a autenticação Bearer já existente do DevPilot.

## Análise

O analisador atual é determinístico e leve para funcionar no perfil de poucos recursos. Ele procura:

- comandos repetidos;
- sequências de 2 a 4 comandos repetidas;
- cliques recorrentes na mesma região/controle;
- atalhos recorrentes;
- coexistência de repetição web + terminal.

O resultado inclui `automation_score`, resumo, padrões e até oito candidatos de automação. Nenhum candidato é executado automaticamente nesta etapa.

## Próxima evolução prevista

O passo seguinte pode converter um candidato escolhido em uma tarefa DevPilot parametrizada, mantendo aprovação, auditoria e rollback antes de qualquer execução real.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

