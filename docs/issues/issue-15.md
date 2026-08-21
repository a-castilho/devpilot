# Issue #15 — segurança: desativar acesso bootstrap permanente após primeiro administrador

> Documento gerado automaticamente a partir da issue. Edite a issue no GitHub; este arquivo será sincronizado novamente.

## Metadados

- **Status:** Fechada
- **Autor:** @acastilho
- **Responsáveis:** —
- **Labels:** —
- **Milestone:** —
- **Criada em:** 2026-08-20T12:16:54Z
- **Atualizada em:** 2026-08-21T01:17:18Z
- **Fonte:** https://github.com/a-castilho/devpilot/issues/15

## Planejado / descrição da issue

## Achado da auditoria automática

A autenticação por e-mail/senha foi adicionada, porém `current_principal()` continua aceitando `DEVPILOT_BOOTSTRAP_TOKEN` em todas as requisições e o converte em um principal `SUPER_ADMIN`, mesmo depois de o primeiro usuário persistente já ter sido criado.

Isso mantém uma credencial administrativa paralela e permanente enquanto o token estiver configurado no ambiente.

## Risco
- acesso SUPER_ADMIN fora do ciclo normal de usuários/RBAC;
- revogação de usuário não revoga o bootstrap;
- um segredo antigo de bootstrap comprometido continua válido;
- a UI ainda oferece “Acesso técnico por token”.

## Correção esperada
- aceitar o bootstrap somente enquanto não houver usuário persistente, ou exigir um modo explícito de recuperação temporária;
- após bootstrap concluído, rejeitar esse token nos endpoints normais;
- remover/ocultar o acesso técnico por token na UI quando `bootstrap_required=false`;
- cobrir com testes: primeiro acesso permitido, pós-bootstrap rejeitado, recuperação controlada se existir;
- documentar rotação/remoção de `DEVPILOT_BOOTSTRAP_TOKEN` em produção.

## Critério de aceite
Depois que existir ao menos um usuário ativo, o token de bootstrap sozinho não pode autenticar uma sessão SUPER_ADMIN normal.

## Regra de revisão

A PR deve referenciar esta issue e comparar **planejado x implementado x resultado observável/tela**. Mudanças visuais exigem evidência antes/depois; mudanças não visuais exigem evidência equivalente.
