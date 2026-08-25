# Boot de frontend em máquinas de pouca memória

O DevPilot mantém a tela de autenticação deliberadamente leve. Antes do login, somente o bootstrap principal (`app.js`) e a autenticação (`auth-ui.js`) executam.

Após existir um `devpilot-token`, os módulos de dashboard, voz, jogo, telemetria e administração são carregados em sequência. Isso reduz picos de compilação JavaScript, registros simultâneos de `MutationObserver` e rajadas de requisições durante a tela de acesso.

A regra é de desempenho, não de autorização: todos os endpoints continuam protegidos pelo backend. O carregamento tardio apenas evita trabalho de UI que não tem utilidade antes da autenticação.
