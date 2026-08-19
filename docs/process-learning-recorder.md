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
http://127.0.0.1:8081/telemetry
```

A tela oferece botões de 1, 2 e 5 minutos. A API aceita sessões entre 10 segundos e 60 minutos.

Durante a gravação, a sessão continua ativa no backend mesmo ao voltar para o dashboard principal. O dashboard recebe um capturador leve que consulta a sessão ativa e envia somente os eventos permitidos.

## Ativar captura de terminal

No repositório DevPilot:

```bash
export DEVPILOT_URL=http://127.0.0.1:8081
export DEVPILOT_BOOTSTRAP_TOKEN='seu-token-real'
source tools/devpilot_terminal_capture.sh
```

O hook é instalado apenas no shell Bash em que o arquivo foi carregado. Para tornar permanente, as três linhas podem ser adicionadas ao ambiente de inicialização escolhido pelo operador, mantendo o token fora do Git.

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
