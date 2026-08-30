# Ciclo de vida de credenciais de provedores de IA

## Objetivo

Estabelecer o padrão funcional e arquitetural para cadastro, persistência, validação e revalidação de credenciais de provedores de IA no DevPilot.

O princípio central é simples:

> A credencial é cadastrada uma vez e passa a ser responsabilidade do DevPilot preservá-la com segurança. Falhas transitórias de validação não podem apagar a credencial nem obrigar o usuário a cadastrá-la novamente.

Este padrão é provider-agnostic e deve ser aplicado a OpenAI e a qualquer outro provedor integrado ao DevPilot.

## Invariantes

1. **Cadastro durável**
   - Após o usuário enviar uma credencial válida em formato aceito pelo DevPilot, o sistema deve persistir o segredo de forma segura antes de tratar falhas transitórias externas como motivo para descarte.
   - Reinício do processo, restart do serviço ou nova sessão do usuário não podem provocar perda da credencial.

2. **Sem recadastro por falha transitória**
   - Timeout, indisponibilidade de rede, DNS, erro 5xx do provedor, rate limit ou indisponibilidade temporária do catálogo não podem apagar a credencial.
   - Nesses casos, a credencial permanece registrada e muda para `pending_validation`.

3. **Validação conclusiva separada de persistência**
   - Persistir a credencial e confirmar se ela está operacional são responsabilidades distintas.
   - Uma falha de validação não pode ser interpretada automaticamente como falha de armazenamento.

4. **Erro conclusivo preserva o registro**
   - Mesmo quando o provedor responde de forma conclusiva que a credencial não é utilizável, o DevPilot não deve apagar o registro silenciosamente.
   - A credencial muda para `invalid` e a interface informa a causa sanitizada.
   - O usuário pode substituir a credencial quando desejar.

5. **Segredo nunca retorna ao cliente**
   - A API nunca devolve a chave em texto puro.
   - Logs, auditoria, mensagens de erro e telemetria nunca incluem a chave, header `Authorization` ou corpo bruto de erro do provedor.

## Estados formais

### `active`

A credencial está persistida e uma validação recente confirmou que o provedor aceitou a autenticação e permitiu a operação necessária para o fluxo configurado.

Exemplos:
- catálogo de modelos acessível;
- chamada de validação oficial concluída com sucesso.

### `pending_validation`

A credencial está persistida, mas o DevPilot não conseguiu concluir a validação por uma causa não conclusiva.

Exemplos:
- timeout;
- erro de rede;
- indisponibilidade do provedor;
- HTTP 429;
- HTTP 5xx;
- falha temporária de DNS;
- erro operacional do catálogo que não prova invalidez da credencial.

Comportamento obrigatório:
- manter a credencial;
- não solicitar recadastro;
- sinalizar que a validação está pendente;
- permitir revalidação posterior automática ou manual.

### `invalid`

A credencial está persistida, mas uma resposta conclusiva indica que ela não pode ser utilizada na configuração atual.

Exemplos:
- HTTP 401: falha de autenticação;
- HTTP 403: acesso necessário negado pela política/permissão do projeto ou da chave;
- formato local definitivamente inválido antes da chamada externa.

Comportamento obrigatório:
- não apagar o registro silenciosamente;
- não marcar como ativa;
- mostrar mensagem sanitizada;
- oferecer atualização/substituição da credencial.

## Transições

```text
novo cadastro
    |
    v
persistido
    |
    +-- validação bem-sucedida -----------------> active
    |
    +-- falha transitória ----------------------> pending_validation
    |
    +-- falha conclusiva -----------------------> invalid

pending_validation
    |
    +-- revalidação bem-sucedida --------------> active
    +-- nova falha transitória -----------------> pending_validation
    +-- falha conclusiva -----------------------> invalid

invalid
    |
    +-- credencial substituída -----------------> pending_validation/active
    +-- permissões externas corrigidas + retry -> active
```

## Semântica de erros do provedor

O status HTTP exposto pela API do DevPilot não deve ser confundido com o status recebido do provedor.

O adapter deve preservar semântica suficiente para decisão de domínio por meio de dados sanitizados, por exemplo:

- `authentication_failed` + `upstream_status=401`;
- `catalog_forbidden` + `upstream_status=403`;
- `rate_limited` + `upstream_status=429`;
- `provider_unreachable`;
- `provider_http_error`;
- `invalid_catalog`;
- `empty_catalog`.

O corpo bruto da resposta externa não deve ser propagado para UI, logs ou auditoria.

## Persistência

A camada de persistência deve armazenar, no mínimo:

- identificador do provedor;
- referência ao usuário/workspace proprietário;
- segredo criptografado;
- estado atual (`active`, `pending_validation`, `invalid`);
- `last_validated_at` quando aplicável;
- código sanitizado da última validação;
- `upstream_status` quando seguro e útil;
- timestamps de criação e atualização.

O segredo deve continuar criptografado em repouso e nunca ser retornado pela API.

## Revalidação

A revalidação pode ocorrer:

- imediatamente após cadastro;
- quando o usuário solicita atualização de modelos;
- antes de uma operação que dependa da credencial;
- por rotina assíncrona de manutenção;
- após uma credencial em `pending_validation` atingir o próximo ciclo de retry.

Retries devem usar backoff e não podem transformar indisponibilidade temporária em recadastro obrigatório.

## Interface

A UI deve refletir o estado real sem expor segredo:

- `active`: **Conectado**;
- `pending_validation`: **Cadastrado · validação pendente**;
- `invalid`: **Credencial precisa de atenção**.

Ações esperadas:

- `active`: atualizar credencial opcionalmente;
- `pending_validation`: tentar validar novamente e permitir substituição opcional;
- `invalid`: atualizar credencial ou, quando aplicável, corrigir permissões externas e tentar novamente.

A interface não deve usar uma falha transitória como gatilho para limpar o campo persistido ou voltar ao estado de "credencial ausente".

## Segurança e observabilidade

É permitido registrar:

- provedor;
- estado da credencial;
- código de erro de domínio;
- status HTTP upstream sanitizado;
- timestamps;
- identificadores internos não secretos.

É proibido registrar:

- API key;
- token;
- header `Authorization`;
- corpo bruto de erro do provedor;
- qualquer payload que possa conter o segredo.

## Critérios de aceite

A implementação do ciclo de vida é considerada correta quando, no mínimo:

1. uma credencial cadastrada continua registrada após restart do DevPilot;
2. timeout durante validação resulta em `pending_validation` sem perda do segredo;
3. HTTP 429 resulta em `pending_validation` sem recadastro;
4. HTTP 5xx resulta em `pending_validation` sem recadastro;
5. HTTP 401 resulta em `invalid` com `authentication_failed`;
6. HTTP 403 resulta em `invalid` com `catalog_forbidden`;
7. revalidação bem-sucedida promove `pending_validation` ou `invalid` para `active` quando a causa externa foi resolvida;
8. nenhum endpoint retorna a chave em texto puro;
9. logs e auditoria não contêm segredo nem corpo bruto do provedor;
10. a UI nunca apresenta "credencial ausente" apenas porque uma revalidação transitória falhou.

## Relação com a correção do PR #147

O PR #147 corrige a primeira parte deste padrão: preserva a semântica das respostas do provedor e diferencia autenticação (`401`) de autorização/permissão (`403`) sem vazar dados sensíveis.

A evolução seguinte deve aplicar os estados formais deste documento ao armazenamento e ao fluxo de revalidação, garantindo definitivamente o princípio de **cadastrar uma vez e não exigir novo cadastro por falha transitória**.
