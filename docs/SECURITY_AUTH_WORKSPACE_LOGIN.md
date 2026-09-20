# Isolamento de workspace no login

## Problema

O modelo de usuário permite o mesmo e-mail em workspaces diferentes por meio da unicidade composta `(workspace_id, email)`. O endpoint de login, porém, recebia apenas e-mail e senha e buscava uma única linha por e-mail sem escopo de workspace.

Esse comportamento era inseguro em instalações multi-workspace: a seleção podia depender da ordem retornada pelo banco e não havia garantia de que o token seria emitido para o tenant correto.

## Regra de segurança

Enquanto o contrato público de login continuar sendo somente `email + password`, o DevPilot não pode escolher um workspace arbitrariamente.

A resolução agora segue estas regras:

- todos os usuários com o e-mail normalizado são considerados;
- a senha é validada apenas como credencial de autenticação, sem inferir tenant por ordem de consulta;
- somente contas ativas e com hash de senha válido podem ser candidatas;
- um token é emitido somente quando existe exatamente uma conta ativa compatível com a senha informada;
- zero correspondências e múltiplas correspondências retornam o mesmo `401` genérico;
- nenhuma informação sobre existência de outro workspace é exposta na resposta pública;
- o token continua carregando `workspace_id` da única conta autenticada.

## Compatibilidade

Não há migration, alteração de schema ou mudança no payload de `/api/auth/login`.

Instalações com e-mails globalmente únicos mantêm o comportamento anterior. Se o mesmo e-mail existir em vários workspaces com senhas diferentes, a senha pode identificar uma única conta. Se duas contas ativas compartilharem o mesmo e-mail e a mesma senha, o login falha fechado em vez de escolher um tenant arbitrariamente.

## Limitação conhecida

O produto ainda não oferece seletor explícito de workspace no contrato de login. Portanto, credenciais idênticas em mais de um workspace permanecem deliberadamente não autenticáveis pelo fluxo atual.

Uma evolução futura pode adicionar um identificador de workspace explícito ao login. Essa mudança deve ser tratada como alteração de contrato e experiência de autenticação, com validação de enumeração de contas, rate limiting e compatibilidade dos clientes existentes.

## Validação esperada

A suíte crítica `auth` inclui regressões para:

- mesmo e-mail em dois workspaces com senhas diferentes;
- mesmo e-mail e mesma senha em dois workspaces, que deve falhar fechado;
- duplicata inativa que não deve bloquear uma correspondência ativa única;
- comportamento existente de login, bootstrap e sessão.
