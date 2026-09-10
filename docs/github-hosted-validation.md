# Validação independente do Linux local

## Objetivo

Permitir que o DevPilot continue sendo desenvolvido e validado no GitHub mesmo quando o Linux local do usuário estiver desligado, desconectado da rede ou com o runner self-hosted indisponível.

A validação hospedada complementa, mas não substitui, o teste local. Ela cobre código, contratos e política de engenharia sem depender de processos, banco ou rede da máquina do usuário.

## Workflow

Arquivo: `.github/workflows/hosted-validation.yml`

Nome: `DevPilot Hosted Validation`

Runner: `ubuntu-latest` fornecido pelo GitHub Actions.

O workflow é executado em pull requests e também pode ser iniciado manualmente por `workflow_dispatch`.

## O que o gate valida

1. Checkout completo do repositório para cálculo correto do diff de política.
2. Python 3.12.
3. Instalação do pacote e dependências de teste com `.[test]`.
4. Política de engenharia via `scripts/check-engineering-standards.py --changed`.
5. Compilação dos fontes Python e testes com `compileall`.
6. Testes unitários e de contrato com `pytest`, excluindo apenas testes marcados `browser_e2e`.

## O que não depende do Linux local

O gate não utiliza:

- `/home/xx/Documents/devpilot`;
- runner self-hosted;
- banco SQLite local;
- processos locais da API ou worker;
- porta `8080` da máquina do usuário;
- IP da rede local;
- credenciais locais não presentes no GitHub.

Assim, desligar o computador local não bloqueia a validação básica das alterações em código.

## O que continua exigindo teste local

Os seguintes itens continuam pertencendo ao gate de integração local:

- atualização real do checkout em `/home/xx/Documents/devpilot`;
- preservação do banco e do ambiente de runtime;
- inicialização da API e do worker reais;
- acesso pela LAN, por exemplo `192.168.x.x:8080`;
- integração com processos e serviços instalados na máquina;
- credenciais armazenadas apenas no ambiente local;
- comportamento real do navegador do celular contra o servidor local.

## Fluxo recomendado

Durante desenvolvimento:

`alteração -> PR -> Hosted Validation -> correções -> Hosted Validation verde`

Quando o Linux estiver disponível:

`Hosted Validation verde -> atualização local -> API/worker -> healthcheck -> teste mobile -> aprovação final`

## Regra de entrega

Uma alteração não deve ser considerada validada localmente apenas porque o gate hospedado passou.

O significado dos gates é:

- **Hosted Validation verde:** código e contratos básicos estão consistentes em ambiente limpo e reproduzível.
- **Local Validation verde:** o DevPilot funciona na instalação real do usuário.
- **Entrega pronta:** os gates exigidos para o tipo de mudança estão verdes e existe evidência suficiente para o objetivo da alteração.

## Segurança

O workflow hospedado não acessa a máquina local e não tenta copiar credenciais do usuário. Ele utiliza apenas permissões de leitura do repositório e dependências públicas necessárias aos testes.

Esse isolamento reduz o acoplamento entre CI e estação de trabalho e permite continuar a investigação e desenvolvimento mesmo quando o Linux local estiver indisponível.
