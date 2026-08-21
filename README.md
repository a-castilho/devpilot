# DevPilot — consultor de desenvolvimento com IA

DevPilot é uma plataforma SaaS leve para analisar, orientar e automatizar a evolução de projetos de software. Ele atua como um consultor de desenvolvimento: entende o contexto de cada projeto, identifica falhas, riscos e oportunidades, transforma o diagnóstico em recomendações compreensíveis e, quando autorizado, executa correções com acompanhamento completo.

A plataforma centraliza vários projetos e tarefas em um painel responsivo, recebe instruções por texto, API ou voz, aplica as regras do projeto, trabalha em ambientes Git isolados e mantém cada decisão, aprovação e execução em uma trilha de auditoria.

## Proposta de valor

O DevPilot reduz o trabalho manual entre descobrir um problema e entregar uma solução segura:

- analisa código, configuração, arquitetura, testes e histórico Git;
- apresenta diagnóstico, impacto, prioridade e recomendação em linguagem clara;
- gera uma proposta de correção compatível com o contexto e o valor do projeto;
- transforma análises aprovadas em tarefas rastreáveis, sem duplicá-las;
- executa trabalho em branch e diretório isolados;
- acompanha os estados da tarefa, da fila ao resultado;
- preserva controle humano para ações sensíveis;
- registra comandos, decisões, aprovações, resultados e falhas.

## Princípios do produto

- **Consultoria antes da execução:** explicar o problema e a solução antes de alterar o projeto.
- **Controle humano:** push, merge, deploy, dependências, migrações destrutivas e produção exigem autorização explícita.
- **Isolamento:** dados, credenciais, repositórios e execuções não podem atravessar organizações ou projetos.
- **Rastreabilidade:** toda ação relevante deve ser atribuível, revisável e auditável.
- **Reversibilidade:** alterações devem ocorrer em branches exclusivas e ser reversíveis sempre que possível.
- **Segurança por padrão:** entradas, transcrições e conteúdos de repositórios são tratados como não confiáveis.
- **Eficiência:** interface e operação devem continuar úteis em máquinas com pouca memória.

## O que o MVP entrega

- dashboard responsivo/PWA para desktop e celular;
- autenticação por e-mail e senha, usuários, organizações e perfis de acesso;
- cadastro de projetos com repositório, branch, contexto e perfil do Codex;
- análise técnica com resumo, riscos, recomendações, gráficos e logs;
- tarefas criadas pelo dashboard, voz ou API;
- fila persistente com worker independente ou incorporado;
- aprovação humana conforme risco;
- executor Codex com argumentos seguros, diretório fixo e timeout;
- cofre criptografado para credenciais de provedores;
- auditoria encadeada por hash;
- política de hosts Git permitidos e diretórios isolados;
- Docker Compose com aplicação, worker e PostgreSQL;
- SQLite para desenvolvimento local leve.

## Arquitetura

```text
Painel/PWA
   │ texto, voz, análise e aprovação
FastAPI ── autenticação/política ── auditoria hash-chain
   │                                  │
PostgreSQL ou SQLite                  vault criptografado
   │
fila/worker ── worktree isolada ── Codex CLI ── branch/PR
```

O backend usa Python 3.12, FastAPI, SQLAlchemy e Pydantic Settings. A interface é servida pela própria aplicação a partir de `app/static`. Em produção, aplicação e worker usam PostgreSQL; no desenvolvimento local, SQLite evita infraestrutura desnecessária.

## Fluxo de análise e correção

1. O usuário seleciona o projeto e informa o objetivo por texto, voz ou API.
2. O DevPilot captura as instruções e o contexto técnico sem expor segredos.
3. A análise somente leitura produz resumo, evidências, riscos e recomendações.
4. O usuário revisa o diagnóstico e autoriza a correção quando necessário.
5. O sistema cria uma única tarefa, impedindo duplicação da mesma ação.
6. O worker prepara um ambiente isolado, aplica as regras do projeto e chama o Codex.
7. Testes, comandos, logs, falhas e resultado ficam associados à execução.
8. Push, PR, merge ou deploy permanecem etapas separadas e controladas.

## Executar localmente

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload --port 8080
```

Em outro terminal, quando o worker incorporado estiver desativado:

```bash
source .venv/bin/activate
python -m app.worker
```

Abra `http://localhost:8080`.

No primeiro acesso, use `DEVPILOT_BOOTSTRAP_TOKEN` somente para criar o primeiro usuário `SUPER_ADMIN`. Depois disso, o acesso normal deve ocorrer por e-mail e senha. O token de bootstrap não é uma sessão administrativa e deve ser removido ou rotacionado após a configuração inicial.

## Docker

```bash
cp .env.example .env
docker compose up -d --build app worker
```

Antes de produção, gere uma chave Fernet e configure `DEVPILOT_ENCRYPTION_KEY`:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Mantenha `DEVPILOT_EXECUTION_ENABLED=false` até o host de execução possuir Codex CLI e Git configurados, credenciais de escopo mínimo e diretório isolado.

## Validação

```bash
python -m compileall app
pytest
```

Após alterações visuais, valide manualmente o painel em desktop e celular, incluindo menu recolhível, modais, rolagem, temas, estados de carregamento e prevenção de chamadas duplicadas.

## Segurança

Nunca envie ao frontend chaves de provedores, tokens Git, segredos de autenticação ou valores brutos do ambiente. Em produção, use KMS/secret manager, tokens curtos, runners sem privilégios e aprovação explícita para ações de risco.

Transcrições de voz, prompts, logs e conteúdo de repositórios são entradas não confiáveis. Redija segredos antes de persistir ou exibir informações e nunca execute texto do usuário como uma string de shell.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**
