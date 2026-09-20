# DevPilot — Documentação Técnica
## Tratamento de falhas na criação de repositórios GitHub

**Status:** Proposta de melhoria  
**Componente:** Integração GitHub / Fluxo de Planejamento  
**Etapa afetada:** Etapa 1/7 — Planejamento  
**Código de erro atual:** `REPOSITORY_NOT_READY`  
**Cenário analisado:** Falha de validação na criação de repositório

---

## 1. Objetivo

Esta documentação descreve o problema identificado no fluxo de criação de repositórios GitHub pelo DevPilot e propõe melhorias de arquitetura, tratamento de erros, retry, autocorreção, observabilidade e experiência do usuário.

O objetivo principal é impedir que falhas determinísticas e autocorrigíveis sejam tratadas como dependências externas ou decisões humanas.

---

## 2. Contexto do problema

Durante a etapa de Planejamento, o DevPilot tentou criar um repositório GitHub e recebeu uma falha de validação relacionada ao campo `description`.

A mensagem apresentada no diagnóstico foi:

```text
Repository creation failed.
description control characters are not allowed
description cannot be more than 350 characters
```

O fluxo foi interrompido após múltiplas tentativas e entrou no estado:

```text
awaiting_approval
```

com o código:

```text
REPOSITORY_NOT_READY
```

---

## 3. Diagnóstico

### 3.1 Causa provável

O payload enviado para a criação do repositório contém uma descrição inválida por um ou mais dos seguintes motivos:

- presença de caracteres de controle;
- quebras de linha não normalizadas;
- tabulações;
- caracteres invisíveis;
- comprimento superior ao limite aceito pelo GitHub.

Exemplo de payload problemático:

```json
{
  "name": "repositorio-exemplo",
  "description": "Descrição extensa gerada automaticamente...\nMais informações..."
}
```

### 3.2 Classificação correta

A falha deve ser classificada como:

```text
Erro de validação de payload
```

e não como:

```text
Erro de credencial
Erro de permissão
Erro transitório
Dependência de decisão humana
```

### 3.3 Problemas no comportamento atual

Foram identificados os seguintes pontos:

1. **Retry cego em erro determinístico**  
   A mesma requisição é repetida sem alteração do payload.

2. **Classificação excessivamente genérica**  
   `REPOSITORY_NOT_READY` não descreve a causa real.

3. **Escalonamento humano prematuro**  
   O fluxo entra em `awaiting_approval` mesmo quando a correção é segura e automática.

4. **Diagnóstico com hipóteses não comprovadas**  
   A interface menciona políticas organizacionais e credenciais sem evidência direta desse problema.

5. **Ausência de validação local prévia**  
   O payload inválido chega até a API externa.

---

## 4. Comportamento esperado

O DevPilot deve validar e normalizar os metadados do repositório antes de chamar a API do GitHub.

Fluxo esperado:

```text
Planejamento
    ↓
Gerar metadados
    ↓
Validar metadados
    ↓
Normalizar / corrigir
    ↓
Validar novamente
    ↓
Chamar API GitHub
    ↓
Classificar resposta
    ↓
Sucesso ou tratamento específico
```

---

## 5. Estratégia de validação

### 5.1 Campo `description`

Antes do envio:

- remover caracteres de controle;
- substituir quebras de linha por espaço;
- compactar espaços consecutivos;
- remover espaços nas extremidades;
- limitar o comprimento;
- impedir envio de valores inválidos.

Exemplo:

```javascript
function sanitizeRepositoryDescription(value = "") {
  return value
    .replace(/[\x00-\x1F\x7F]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 350);
}
```

### 5.2 Recomendação adicional

Utilizar um limite interno conservador, por exemplo:

```text
320 caracteres
```

Isso reduz risco de erros em transformações posteriores e mantém margem operacional.

---

## 6. Taxonomia de erros

A integração deve classificar os erros por natureza.

| Categoria | Exemplo | Retry | Intervenção humana |
|---|---|---:|---:|
| Validação | HTTP 400 / 422 | Não, sem correção | Não |
| Transitório | 502 / 503 / timeout | Sim | Não |
| Rate limit | 429 | Sim, com backoff | Normalmente não |
| Autenticação | 401 | Não | Sim |
| Permissão | 403 | Não | Sim |
| Política organizacional | ruleset / policy | Não | Possivelmente |
| Conflito | 409 | Depende | Depende |
| Recurso existente | nome já utilizado | Não | Pode exigir decisão |

---

## 7. Novo modelo de erro recomendado

Substituir:

```text
REPOSITORY_NOT_READY
```

por um código específico:

```text
GITHUB_REPOSITORY_VALIDATION_FAILED
```

Exemplo de estrutura:

```json
{
  "code": "GITHUB_REPOSITORY_VALIDATION_FAILED",
  "provider": "github",
  "resource": "repository",
  "operation": "create",
  "field": "description",
  "problems": [
    "control_characters",
    "max_length_exceeded"
  ],
  "recoverable": true,
  "automatic_fix": true
}
```

---

## 8. Estratégia de recuperação

### Nível 1 — Correção automática segura

Exemplos:

- sanitização de texto;
- truncamento de descrição;
- remoção de caracteres de controle;
- normalização de whitespace;
- normalização de slug.

Ação:

```text
corrigir → revalidar → tentar novamente
```

Não requer aprovação humana.

### Nível 2 — Alteração com impacto semântico

Exemplos:

- alterar nome do repositório;
- mudar visibilidade;
- remover propriedade obrigatória;
- substituir organização de destino.

Ação:

```text
solicitar aprovação
```

### Nível 3 — Dependência externa

Exemplos:

- credencial inválida;
- SSO pendente;
- permissão insuficiente;
- política organizacional;
- ruleset;
- acesso administrativo.

Ação:

```text
bloquear fluxo e orientar usuário
```

---

## 9. Política de retry

### Não realizar retry automático quando

- o payload estiver inválido;
- o erro for HTTP 400 ou 422 e não houver transformação;
- a autenticação falhar;
- a permissão for negada;
- existir uma regra organizacional explícita.

### Realizar retry quando

- ocorrer timeout;
- ocorrer erro temporário de rede;
- GitHub responder com 502, 503 ou 504;
- houver rate limit e existir informação de espera.

### Exemplo de estratégia

```text
Tentativa 1
   ↓
Erro 422
   ↓
Correção local
   ↓
Tentativa 2
   ↓
Sucesso
```

Evitar:

```text
Tentativa 1 → erro 422
Tentativa 2 → mesmo payload → erro 422
Tentativa 3 → mesmo payload → erro 422
```

---

## 10. Máquina de estados recomendada

Estados sugeridos:

```text
planning
validating_repository_metadata
creating_repository
auto_repairing
retrying
awaiting_user_decision
blocked_external_dependency
completed
failed
```

Transição recomendada para o cenário analisado:

```text
planning
  ↓
validating_repository_metadata
  ↓
auto_repairing
  ↓
creating_repository
  ↓
completed
```

O estado `awaiting_user_decision` só deve ser utilizado quando existir uma escolha genuinamente necessária.

---

## 11. Melhorias na interface

### 11.1 Remover redundância

A mensagem de diagnóstico aparece repetida na interface. Deve existir apenas uma mensagem principal de erro.

### 11.2 Exibir causa objetiva

Em vez de:

```text
Verifique políticas de criação de repositórios, propriedades obrigatórias e permissões.
```

usar:

```text
O GitHub rejeitou a descrição do repositório porque ela contém caracteres inválidos ou excede o limite permitido.
```

### 11.3 Exibir ação automática

Quando a falha for recuperável:

```text
Descrição normalizada automaticamente.
- caracteres de controle removidos;
- comprimento ajustado;
- nova tentativa iniciada.
```

### 11.4 CTA contextual

Quando houver autocorreção disponível, usar:

```text
Corrigir descrição e tentar novamente
```

em vez de somente:

```text
Atualizar diagnóstico
```

---

## 12. Observabilidade

Registrar eventos estruturados.

### Evento de validação

```json
{
  "event": "repository_metadata_validation_failed",
  "provider": "github",
  "field": "description",
  "reason": "max_length_exceeded"
}
```

### Evento de autocorreção

```json
{
  "event": "repository_metadata_auto_repaired",
  "field": "description",
  "actions": [
    "control_characters_removed",
    "whitespace_normalized",
    "truncated"
  ]
}
```

### Evento de retry

```json
{
  "event": "github_operation_retry",
  "operation": "repository.create",
  "attempt": 2,
  "reason": "payload_repaired"
}
```

---

## 13. Segurança e auditoria

A autocorreção deve:

- nunca registrar tokens ou segredos;
- evitar persistência desnecessária do payload completo;
- registrar apenas metadados necessários;
- manter audit trail das transformações;
- distinguir correção técnica de decisão de negócio;
- nunca modificar credenciais automaticamente.

---

## 14. Critérios de aceite

A implementação será considerada correta quando:

- [ ] O DevPilot não enviar descrições acima do limite aceito.
- [ ] Caracteres de controle forem removidos antes da chamada externa.
- [ ] Erros 400/422 não receberem retry cego.
- [ ] O campo responsável pela falha for identificado no diagnóstico.
- [ ] Erros de payload não forem apresentados como falhas de credencial sem evidência.
- [ ] `awaiting_approval` não for utilizado para correções automáticas seguras.
- [ ] A autocorreção for registrada em log estruturado.
- [ ] O usuário receber uma mensagem clara sobre o que foi corrigido.
- [ ] O sistema diferenciar falhas transitórias, permanentes e recuperáveis.
- [ ] Testes automatizados cobrirem descrições inválidas, extensas e com caracteres de controle.

---

## 15. Casos de teste

### CT-01 — Descrição válida

**Entrada:**

```text
API de gerenciamento de pedidos
```

**Esperado:**

- sem alteração;
- criação do repositório segue normalmente.

### CT-02 — Descrição com quebra de linha

**Entrada:**

```text
API de pedidos
Responsável por integração externa
```

**Esperado:**

```text
API de pedidos Responsável por integração externa
```

### CT-03 — Descrição acima do limite

**Esperado:**

- descrição truncada;
- tamanho final dentro do limite;
- operação continua.

### CT-04 — Caracteres de controle

**Esperado:**

- caracteres removidos ou substituídos;
- validação local aprovada.

### CT-05 — Erro 422 após sanitização

**Esperado:**

- não executar retries infinitos;
- registrar erro estruturado;
- exibir motivo retornado pelo GitHub.

### CT-06 — Erro 503

**Esperado:**

- retry com backoff;
- sem intervenção humana imediata.

### CT-07 — Erro 401

**Esperado:**

- não realizar retry cego;
- marcar dependência externa;
- solicitar correção da credencial.

---

## 16. Plano de implementação

### Fase 1 — Validação

Implementar:

- schema de metadados;
- sanitizador;
- validação de comprimento;
- testes unitários.

### Fase 2 — Classificação de erros

Implementar:

- parser de erros GitHub;
- códigos internos específicos;
- propriedade `recoverable`;
- propriedade `automatic_fix`.

### Fase 3 — Recovery engine

Implementar:

- autocorreções seguras;
- retry condicionado;
- backoff para falhas transitórias.

### Fase 4 — UX

Atualizar:

- mensagens;
- CTAs;
- estados;
- detalhamento do diagnóstico.

### Fase 5 — Observabilidade

Adicionar:

- eventos estruturados;
- métricas de falha;
- taxa de autocorreção;
- retries por categoria;
- escalonamentos humanos evitados.

---

## 17. Métricas recomendadas

Monitorar:

```text
github_repository_creation_success_rate
github_repository_validation_failure_rate
repository_metadata_auto_repair_rate
repository_creation_retry_rate
repository_creation_human_escalation_rate
repository_creation_mean_attempts
```

Indicador importante:

```text
percentual de falhas de validação resolvidas sem intervenção humana
```

---

## 18. Decisão arquitetural

A integração deve seguir o princípio:

> Falhas tecnicamente corrigíveis devem ser resolvidas pelo agente antes de interromper o fluxo.

O DevPilot deve distinguir claramente entre:

```text
falha autocorrigível
falha transitória
decisão humana
dependência externa
falha definitiva
```

No cenário analisado, a descrição inválida deve ser tratada como **falha autocorrigível de validação**, e não como uma condição de aprovação humana.

---

## 19. Resultado esperado

Após a implementação, um caso equivalente deve produzir um fluxo semelhante a:

```text
Validação da descrição falhou
        ↓
Descrição normalizada automaticamente
        ↓
Payload validado
        ↓
Nova tentativa de criação
        ↓
Repositório criado
        ↓
Planejamento continua
```

Isso reduz interrupções, elimina retries inúteis e torna o comportamento do DevPilot mais previsível, auditável e resiliente.
