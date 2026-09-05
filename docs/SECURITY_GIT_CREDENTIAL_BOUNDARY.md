# Fronteira de credenciais Git

O DevPilot aceita URLs de repositório somente após `normalize_repository_url`, respeitando `DEVPILOT_ALLOWED_GIT_HOSTS`. A lista de hosts é configuração operacional da instalação e não é escolhida pelo tenant durante a execução.

## Invariantes

- Toda operação Git capaz de acessar a rede revalida a URL persistida antes de clone, fetch ou recuperação de credencial.
- Cada checkout local fica em um caminho isolado por `workspace_id` e identidade do projeto; projetos de tenants diferentes nunca compartilham diretório apenas porque possuem o mesmo slug.
- Credenciais de organizações `provider=github` são tratadas como credenciais de `github.com`. Elas não são anexadas a hosts Git adicionais, mesmo quando esses hosts foram explicitamente permitidos pelo operador.
- Organização e `ProviderCredential` precisam pertencer ao mesmo `workspace_id` do projeto antes que um token seja descriptografado.
- Se um projeto GitHub legado ou criado de forma assíncrona ainda estiver sem `organization_id`, a auto-recuperação pode localizar a organização somente pelo owner da URL validada `github.com/<owner>/<repo>` e somente dentro do mesmo workspace. O vínculo do projeto só é reparado depois que uma credencial ativa desse workspace comprova acesso ao repositório com `git ls-remote`.
- Se `organization_id` já estiver preenchido, ele continua autoritativo: o `external_login` da organização deve corresponder ao owner da URL do repositório. Divergência interrompe a recuperação sem enviar credencial e sem substituir o vínculo automaticamente.
- Uma organização compatível existente apenas em outro workspace nunca é candidata para recuperação; não existe fallback global de organização ou credencial.
- O header HTTP de autenticação é configurado no escopo `https://github.com/`, e não como `http.extraHeader` global.
- Um checkout existente não pode alterar silenciosamente o destino do próximo fetch: o DevPilot lê e normaliza `origin` e interrompe a operação se ele divergir da URL persistida. O executor não reescreve `origin` automaticamente.
- A auto-recuperação usa as mesmas regras de URL, host, credencial e caminho isolado. URL inválida ou host não-GitHub encerra a tentativa sem transmitir credenciais.

## Compatibilidade

Repositórios públicos em hosts adicionais configurados continuam permitidos pela política normal de URL, mas não recebem automaticamente um PAT de uma organização GitHub.com. A integração atual de organizações usa a API pública `api.github.com`, portanto o PAT gerenciado pertence a esse provedor.

Não há mudança de schema, payload de API ou formato persistido de credencial.

Projetos existentes com `organization_id` ausente podem ser reparados de forma aditiva pela auto-recuperação quando a URL do repositório identifica inequivocamente uma organização do mesmo workspace e uma credencial já autorizada comprova acesso. Nenhum token novo é criado e nenhuma autorização é inventada.

A mudança de diretório local é intencional: checkouts antigos baseados somente em slug não são reutilizados automaticamente porque não carregam uma identidade de tenant confiável. O primeiro acesso seguro ao projeto fará um clone no novo diretório isolado. Os diretórios legados podem ser removidos posteriormente por housekeeping explícito depois de validação, nunca durante esta correção.

## Limite de proteção

A validação de URL, o isolamento físico do checkout e a verificação read-only de `origin` protegem a credencial fornecida pelo DevPilot contra valores persistidos legados e alterações locais do remote. Configurações Git maliciosas no próprio host ou comprometimento do sistema operacional permanecem fora dessa fronteira e devem ser tratados pela segurança do runtime Linux.
