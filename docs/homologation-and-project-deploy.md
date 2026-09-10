# Homologação pública e deploy por projeto

## Objetivo

Permitir testar o DevPilot pelo celular mesmo quando o Linux local estiver desligado e tornar o deploy de projetos acessível diretamente pela tela **Projetos**.

## Homologação pública do DevPilot

A branch de teste `fix/mobile-standard-top-back` possui o workflow `Deploy Homolog Preview`, executado em runner hospedado pelo GitHub (`ubuntu-latest`). Ele não depende do runner local.

Fluxo:

1. resolve a URL de homologação em `RENDER_HOMOLOG_BASE_URL` ou usa `https://devpilot-homolog.onrender.com`;
2. se `RENDER_HOMOLOG_DEPLOY_HOOK` estiver configurado, solicita ao Render o deploy do commit atual;
3. aguarda `/health` responder HTTP 200 e identificar o serviço DevPilot;
4. valida a raiz da SPA e confirma que o frontend foi publicado.

A ausência do deploy hook não é tratada como sucesso de publicação: o workflow apenas tenta validar um serviço Render já provisionado. HTTP 404 é falha explícita de provisionamento/URL.

## Botão Deploy em Projetos

Os cards de projeto exibem o botão **Deploy** para Super Admin. O botão não executa comando arbitrário diretamente no navegador. Ele carrega o módulo administrativo existente e abre o painel de deploy já selecionando o projeto correspondente.

A configuração continua usando o fluxo auditável existente em `/api/admin/deployments`: ambiente, branch esperada, diretório, comando permitido e timeout são persistidos no projeto e a execução é enfileirada como host action. Em ambiente local, o host autorizado consome a fila. Essa separação preserva os gates de segurança existentes.

## Segurança

- o botão é restrito a `SUPER_ADMIN` porque as rotas de deploy já exigem esse papel;
- o navegador apenas solicita a operação à API;
- nenhuma credencial é exposta no frontend;
- o deploy público da homologação roda no GitHub-hosted runner;
- o deploy local de projetos continua auditável e sujeito às restrições do host action;
- produção continua separada da homologação.

## Operação com o Linux desligado

Com o Linux desligado continuam disponíveis: GitHub CI, validação hospedada e deploy da homologação pública. Ficam indisponíveis apenas ações que dependem do host local, como execução local de comandos, worker local e acesso LAN em `:8080`.
