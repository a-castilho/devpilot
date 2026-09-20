# Fail-fast de autenticação em ambientes implantados

## Problema

O DevPilot possui valores convenientes para desenvolvimento local, incluindo o bootstrap token padrão `development-only-token-change-me` e `auth_secret` vazio. Esses valores não podem ser aceitos em uma implantação real.

Sem validação antecipada, um processo poderia iniciar com configuração insegura e só falhar quando uma operação de autenticação fosse executada. Em uma base nova, um bootstrap token previsível também poderia comprometer a criação do primeiro Super Admin.

## Regra

`get_settings()` valida a configuração de autenticação antes de preparar diretórios ou continuar o bootstrap do processo.

Ambientes locais reconhecidos são:

- `development`;
- `dev`;
- `local`;
- `test`;
- `testing`;
- `ci`.

Qualquer outro valor de `DEVPILOT_ENV` é tratado como ambiente implantado e deve fornecer:

- `DEVPILOT_AUTH_SECRET` com pelo menos 32 caracteres e diferente dos placeholders conhecidos;
- `DEVPILOT_BOOTSTRAP_TOKEN` com pelo menos 32 caracteres e diferente dos placeholders conhecidos.

Se a validação falhar, o processo encerra com `RuntimeError` antes de preparar os diretórios de runtime. A mensagem informa apenas os nomes das variáveis inválidas e nunca inclui o valor dos segredos.

## Compatibilidade

O comportamento de desenvolvimento local permanece inalterado. Os valores de conveniência continuam aceitos nos ambientes locais listados acima.

O `render.yaml` de homologação já usa `generateValue: true` para `DEVPILOT_BOOTSTRAP_TOKEN` e `DEVPILOT_AUTH_SECRET`, portanto está alinhado com essa regra.

## Fora do escopo

Esta alteração não implementa rate limiting de login e não altera o fluxo de bootstrap, payloads HTTP ou schema de banco.

`DEVPILOT_ENCRYPTION_KEY` permanece com sua validação própria no `Vault`; a validação de formato/boot desse segredo deve ser tratada separadamente para não misturar fronteiras criptográficas nesta mudança.
