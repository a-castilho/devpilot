# Issue #214 — [Codex] Corrigir layout global e responsividade do DevPilot — sem correções página por página

> Documento gerado automaticamente a partir da issue. Edite a issue no GitHub; este arquivo será sincronizado novamente.

## Metadados

- **Status:** Fechada
- **Autor:** @acastilho
- **Responsáveis:** —
- **Labels:** —
- **Milestone:** —
- **Criada em:** 2026-08-29T13:42:05Z
- **Atualizada em:** 2026-08-29T14:18:53Z
- **Fonte:** https://github.com/a-castilho/devpilot/issues/214

## Planejado / descrição da issue

## Objetivo
Corrigir a arquitetura global de layout/responsividade do DevPilot. Não fazer hotfix por página. O problema deve ser resolvido nos componentes/estilos compartilhados para que todas as telas herdem o comportamento correto.

## Evidência atual
Na tela **Central de desenvolvimento / Desenvolvimento** (desktop ~1024px), a tabela está colapsando as colunas e quebrando palavras letra por letra:
- `ORIGEM`, `STATUS`, `PRIORIDADE`, `AÇÃO` aparecem verticalizados;
- botão `Aprovar` quebra em várias linhas;
- coluna de fluxo/ações fica comprimida;
- conteúdo e header não se adaptam corretamente ao espaço restante ao lado da sidebar;
- há excesso de regras mobile/page-specific acumuladas, causando conflito de CSS.

Tratar esse print como sintoma de um problema sistêmico, não como uma tela isolada.

## Regra principal
**Não corrigir página por página.**
Criar/consolidar uma camada global de layout e responsividade e remover/neutralizar regras conflitantes. Correções específicas de uma tela só são aceitáveis quando o componente for realmente exclusivo.

## Arquivos/áreas a auditar primeiro
- `app/static/styles.css`
- `app/static/dashboard-layout-v2.css`
- `app/static/simplified-nav.css`
- `app/static/mobile-hotfix.css`
- `app/static/mobile-route.css`
- `app/static/mobile-one-frame.css`
- `app/static/mobile-typography.css`
- `app/static/mobile-scroll-unlock.css`
- `app/static/project-card-scroll.css`
- `app/static/index.html`
- `app/static/app.js`
- `app/static/feature-loader.js`
- demais CSS/JS que injetem regras globais ou alterem largura/overflow/display em runtime.

## Implementação esperada
1. Mapear as regras globais que controlam `main`, conteúdo, sidebar, header, grids, cards, tabelas e barras de ações.
2. Identificar conflitos de cascade/especificidade entre CSS base, dashboard e arquivos `mobile-*`.
3. Consolidar tokens/regras compartilhadas para:
   - largura útil do conteúdo;
   - `min-width: 0` onde necessário em flex/grid;
   - comportamento de grid/flex;
   - overflow horizontal controlado;
   - tabelas responsivas;
   - barras de ações e botões;
   - tipografia e quebra de palavras.
4. Para tabelas:
   - impedir colunas de encolherem até uma letra por linha;
   - usar `white-space`, `min-width`, `word-break` e `overflow-wrap` adequadamente;
   - envolver tabelas largas em container com `overflow-x: auto` quando necessário;
   - manter cabeçalhos legíveis;
   - não deixar botões da coluna de ações esmagarem.
5. Para botões/ações:
   - nunca quebrar texto em letras isoladas;
   - largura mínima coerente;
   - `flex-wrap` apenas em grupos, não dentro do texto do botão;
   - em telas menores, empilhar ações de forma previsível.
6. Sidebar e conteúdo:
   - sidebar não pode sobrepor o conteúdo;
   - conteúdo deve calcular corretamente o espaço disponível;
   - estado recolhido/expandido deve funcionar sem deslocamentos quebrados.
7. Header:
   - título e ações devem reorganizar-se por breakpoint;
   - sem overflow ou elementos espremidos.
8. Remover regras redundantes/contraditórias que tenham virado uma cadeia de hotfixes.
9. Preservar o tema escuro atual e a identidade visual do DevPilot.

## Breakpoints mínimos a validar
- 1920x1080
- 1366x768
- 1024x768
- 768x1024
- 430x932
- 390x844
- 375x667

## Critérios de aceite globais
- Nenhuma palavra de cabeçalho aparece verticalizada letra por letra.
- Nenhum botão quebra texto em caracteres isolados.
- Nenhum conteúdo principal fica escondido pela sidebar.
- Nenhum card/tabela força a página inteira a ultrapassar a viewport.
- Tabelas largas usam scroll horizontal interno quando necessário.
- Header e barras de ação continuam utilizáveis em todos os breakpoints.
- Desktop não recebe comportamento destinado exclusivamente ao mobile.
- Mobile não depende de zoom para leitura/operação.
- O mesmo padrão deve funcionar nas principais rotas sem CSS específico novo para cada página.

## Auditoria obrigatória das telas
Percorrer as principais telas/rotas do DevPilot após a correção, procurando regressões de layout. Não é necessário criar correção individual para cada rota; a navegação serve para validar a solução global.

Priorizar pelo menos:
- Dashboard/Home
- Desenvolvimento/Tarefas
- Projetos
- Chat IA / voz
- Novo projeto / Project Builder
- Super Admin
- RAG Admin
- Linux
- Relatórios/telemetria quando disponíveis

## Testes
Adicionar uma verificação automatizada de regressão responsiva se a infraestrutura existente permitir (preferência Playwright/browser tests). Pelo menos:
- carregar rotas principais;
- verificar ausência de overflow global inesperado;
- verificar elementos críticos visíveis;
- capturar screenshots em breakpoints representativos.

Se testes E2E não estiverem disponíveis, criar uma checagem leve reutilizável e documentar a validação manual realizada.

## Restrições
- Não alterar regras de negócio.
- Não remover funcionalidades.
- Não mascarar o problema com `overflow: hidden` no `body`.
- Não adicionar dezenas de `!important`.
- Não criar um novo `*-fix.css` para cada página.
- Preferir simplificação e consolidação da cascade existente.

## Entrega
1. Implementar a correção global.
2. Rodar testes existentes + validação responsiva.
3. Documentar os conflitos encontrados e quais arquivos/regras foram consolidados/removidos.
4. Commitar a solução.
5. Abrir PR para `main` com resumo, testes executados e evidências dos breakpoints verificados.

**Definição de pronto:** o DevPilot deixa de exigir correção visual página por página; novas e antigas telas passam a herdar um shell/layout responsivo consistente.

## Regra de revisão

A PR deve referenciar esta issue e comparar **planejado x implementado x resultado observável/tela**. Mudanças visuais exigem evidência antes/depois; mudanças não visuais exigem evidência equivalente.
