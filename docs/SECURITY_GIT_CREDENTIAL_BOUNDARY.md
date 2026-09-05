# Fronteira de credenciais Git

O DevPilot aceita URLs de repositório somente após `normalize_repository_url`, respeitando `DEVPILOT_ALLOWED_GIT_HOSTS`. A lista de hosts é configuração operacional da instalação e não é escolhida pelo tenant durante a execução.

## Invariantes

- Toda operação Git capaz de acessar a rede revalida a URL persistida antes de clone, fetch ou recuperação de credencial.
- Credenciais de organizações `provider=github` são tratadas como credenciais de `github.com`. Elas não são anexadas a hosts Git adicionais, mesmo quando esses hosts foram explicitamente permitidos pelo operador.
- Organização e `ProviderCredential` precisam pertencer ao mesmo `workspace_id` do projeto antes que um token seja descriptografado.
- O header HTTP de autenticação é configurado no escopo `https://github.com/`, e não como `http.extraHeader` global.
- Um checkout local existente não controla o destino do próximo fetch: `origin` é realinhado à URL persistida e validada antes da chamada de rede.
- A auto-recuperação usa as mesmas regras. URL inválida ou host não-GitHub encerra a tentativa sem transmitir credenciais.

## Compatibilidade

Repositórios públicos em hosts adicionais configurados continuam permitidos pela política normal de URL, mas não recebem automaticamente um PAT de uma organização GitHub.com. A integração atual de organizações usa a API pública `api.github.com`, portanto o PAT gerenciado pertence a esse provedor.

Não há mudança de schema, payload de API ou formato persistido de credencial.

## Limite de proteção

A validação de URL e o realinhamento de `origin` protegem a credencial fornecida pelo DevPilot contra valores persistidos legados e alterações locais do remote. Configurações Git maliciosas no próprio host ou comprometimento do sistema operacional permanecem fora dessa fronteira e devem ser tratados pela segurança do runtime Linux.
