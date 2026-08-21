# DevPilot — Arquitetura, padrões e uso de IA

**Data de referência:** 21/08/2026

Este documento descreve a arquitetura efetivamente observada no repositório, com foco em automação, agentes, modelos de IA, voz, execução e segurança.

## 1. Visão geral

O DevPilot é uma plataforma para automatizar tarefas de desenvolvimento por dashboard, API ou voz. O sistema organiza projetos, tarefas, políticas, credenciais, execução isolada e auditoria.

Fluxo arquitetural resumido:

```text
PWA / API / Voz
      ↓
FastAPI
      ↓
Política + Aprovação + Auditoria
      ↓
Fila persistente
      ↓
Worker
      ↓
Repositório isolado
      ↓
Codex CLI
      ↓
Git / branch / resultado
```

## 2. Stack principal

### Backend

- Python 3.12+
- FastAPI
- Uvicorn
- SQLAlchemy 2
- Pydantic Settings
- HTTPX
- Cryptography
- python-multipart

### Persistência

- PostgreSQL em Docker/produção
- SQLite como padrão de desenvolvimento local

### Infraestrutura

- aplicação FastAPI;
- worker independente;
- PostgreSQL 16;
- volume persistente para dados e repositórios;
- diretório dedicado para `host-actions`;
- Docker Compose.

## 3. Organização arquitetural

O repositório separa responsabilidades em módulos como:

- rotas de autenticação, usuários, deploy, tarefas e voz;
- `services/` para auditoria, executor, políticas, Git, providers, recovery e vault;
- `worker.py` para consumo da fila;
- `models.py` para persistência;
- `security.py` para controles de acesso;
- `telemetry.py` para observabilidade e rastreamento.

## 4. Agente de desenvolvimento

O principal agente de execução de software é o **Codex CLI**.

O executor monta comandos no formato:

```text
codex exec --json [--model MODEL] PROMPT
```

O DevPilot não trata o modelo como uma função interna isolada: ele delega a execução de desenvolvimento a um agente externo de código, mantendo o próprio sistema responsável por:

- contexto do projeto;
- política;
- aprovação;
- isolamento;
- credenciais;
- auditoria;
- persistência do resultado.

## 5. Segurança e isolamento do agente

O executor implementa práticas relevantes para uso seguro de agentes:

- execução via `subprocess` sem shell;
- timeout configurável;
- clone/fetch controlado;
- isolamento de repositórios;
- worktree descartável para análises read-only;
- preflight obrigatório contra duplicação de implementação;
- instruções `AGENTS.md`;
- redação de segredos em conteúdo gerado;
- separação entre análise e alteração de código;
- push/merge/deploy tratados como operações de risco separadas.

## 6. Modelos e provedores

O DevPilot possui uma camada real de descoberta e gerenciamento de modelos.

Provedores suportados no catálogo verificado:

- OpenAI;
- Anthropic;
- Google.

O serviço consulta dinamicamente as APIs dos provedores para descobrir modelos disponíveis e mantém um catálogo de referência para recomendação.

Isso é uma **abstração de provedor/modelo**, mas não significa que todas as tarefas sejam executadas por qualquer provedor de forma intercambiável. O agente de desenvolvimento verificado continua sendo o Codex CLI.

## 7. Voz e transcrição

A transcrição server-side usa modelos generativos/ASR de forma explícita.

### Primário

OpenAI:

- endpoint `/v1/audio/transcriptions`;
- modelo `gpt-4o-mini-transcribe`;
- idioma configurado como português.

### Fallback

Google Gemini:

- envio de áudio inline;
- prompt específico para transcrição em português do Brasil;
- seleção de modelos Gemini compatíveis;
- fallback automático quando a transcrição OpenAI falha e existe credencial Google ativa.

## 8. Interpretação do comando de voz

A etapa posterior à transcrição é, no código verificado, predominantemente determinística.

`intent.py` usa regex e palavras-chave para identificar intenções como:

- atualizar ambiente local;
- iniciar projeto;
- analisar projeto;
- desenvolver tarefa;
- extrair dica de projeto.

Portanto:

```text
Áudio → modelo de transcrição → texto → regras/regex → intenção → política → execução
```

A interpretação de intenção não deve ser descrita hoje como classificação por LLM.

## 9. RAG

**Não foi observado um pipeline RAG clássico implementado no DevPilot.**

O Codex recebe contexto do projeto e pode operar sobre o repositório, mas isso não equivale automaticamente a RAG.

Para caracterizar RAG seria necessário observar explicitamente um pipeline como:

```text
Documentos → chunks → embeddings → vector store → retrieval → prompt → geração
```

Esse fluxo não foi identificado como componente arquitetural próprio do DevPilot.

## 10. Padrões de IA e automação

Os padrões mais relevantes são:

- agente externo para execução de código;
- orquestrador próprio para segurança e governança;
- humano no circuito para ações sensíveis;
- fallback entre provedores na transcrição;
- vault criptografado para credenciais;
- isolamento read-only para análise;
- trilha de auditoria;
- separação entre compreensão do comando e execução da tarefa.

## 11. Resumo executivo

O DevPilot usa IA em camadas distintas. O Codex CLI atua como agente de desenvolvimento, OpenAI e Gemini são usados na camada de transcrição, e a interpretação básica da intenção de voz continua determinística. A arquitetura evita transformar o LLM no controlador absoluto do sistema: política, credenciais, auditoria, isolamento, autorização e persistência permanecem sob responsabilidade do DevPilot.
