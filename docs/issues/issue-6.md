# Issue #6 — homologação: validar central de Relatórios na tela

> Documento gerado automaticamente a partir da issue. Edite a issue no GitHub; este arquivo será sincronizado novamente.

## Metadados

- **Status:** Aberta
- **Autor:** @acastilho
- **Responsáveis:** —
- **Labels:** —
- **Milestone:** —
- **Criada em:** 2026-08-19T17:26:31Z
- **Atualizada em:** 2026-08-19T17:26:31Z
- **Fonte:** https://github.com/a-castilho/devpilot/issues/6

## Planejado / descrição da issue

## Objetivo
Validar em homologação a nova área **Relatórios** do DevPilot e registrar evidência de que o comportamento implementado corresponde à interface entregue.

## Implementado
- [x] item Relatórios no menu
- [x] leitura por categorias e busca
- [x] Copiar para conversa
- [x] atalho Nova ideia
- [x] geração automática a partir de documentação permitida
- [x] sanitização de padrões sensíveis
- [x] relatório removido de `/assets`
- [x] API `/api/project-report` protegida por autenticação

## Segurança
A projeção fica fora da pasta estática. O navegador recebe o conteúdo somente pela API autenticada do DevPilot; o GitHub privado não é consultado diretamente pelo frontend.

## Critérios pendentes
- [ ] abrir a área Relatórios na homologação real
- [ ] registrar screenshot/evidência visual desktop
- [ ] registrar screenshot/evidência visual mobile
- [ ] testar busca e categorias
- [ ] testar Copiar para conversa
- [ ] confirmar 404 para a antiga cópia em `/assets/project-report.json`
- [ ] comparar planejado x implementado x tela real

Referência: `docs/ideas/RELATORIOS_HOMOLOGACAO_VALIDACAO.md`.

## Regra de revisão

A PR deve referenciar esta issue e comparar **planejado x implementado x resultado observável/tela**. Mudanças visuais exigem evidência antes/depois; mudanças não visuais exigem evidência equivalente.
