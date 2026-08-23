(() => {
  const PANEL_ID = 'investia-admin-view';

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function value(form, name) {
    return form?.elements?.[name]?.value ?? '';
  }

  function buildHomologationText() {
    const panel = document.getElementById(PANEL_ID);
    const form = panel?.querySelector('#investia-project-form');
    if (!panel || !form) return '';

    const projectName = panel.querySelector('#investia-title')?.textContent?.trim() || 'Projeto não selecionado';
    const publication = panel.querySelector('#devai-publication-badge')?.textContent?.trim() || 'NÃO PUBLICADO';
    const status = value(form, 'status');
    const now = new Date().toLocaleString('pt-BR');

    return [
      'DEVAI INVEST — INFORMAÇÕES DE HOMOLOGAÇÃO',
      `Gerado em: ${now}`,
      '',
      `Projeto: ${projectName}`,
      `Chave externa: ${value(form, 'external_project_key')}`,
      `Moeda: ${value(form, 'currency')}`,
      `Status do projeto: ${status}`,
      `Publicação: ${publication}`,
      '',
      'REGRA FINANCEIRA',
      `Meta de captação: ${value(form, 'funding_target')}`,
      `Captação mínima: ${value(form, 'minimum_funding')}`,
      `Captação máxima: ${value(form, 'maximum_funding')}`,
      `Investimento mínimo: ${value(form, 'minimum_investment')}`,
      `Máximo por investidor: ${value(form, 'maximum_investment_per_user') || 'sem limite'}`,
      `% do líquido aos investidores: ${value(form, 'investor_share_percentage')}%`,
      '',
      'CHECKLIST DE HOMOLOGAÇÃO',
      '[ ] Alterar um valor, salvar, recarregar a página e confirmar persistência.',
      '[ ] Pausar a publicação, recarregar e confirmar status PAUSADO.',
      '[ ] Publicar novamente e confirmar status PUBLICADO.',
      '[ ] Validar captação mínima maior que a máxima — deve ser rejeitada.',
      '[ ] Validar investimento mínimo maior que o máximo por investidor — deve ser rejeitado.',
      '[ ] Validar percentual acima de 100 — deve ser rejeitado.',
      '[ ] Remover do DevAI Invest e confirmar que o projeto continua no DevPilot.',
      '[ ] Acessar como usuário comum e confirmar bloqueio do menu e da API administrativa.',
      '[ ] Confirmar que o projeto publicado aparece na área pública do investidor.',
      '[ ] Executar simulação de distribuição líquida e conferir cálculo.',
      '',
      'RESULTADO',
      'Responsável: ______________________________',
      'Data: _____________________________________',
      'Status: [ ] APROVADO  [ ] REPROVADO',
      'Observações: ______________________________',
    ].join('\n');
  }

  async function copyText(text, button) {
    try {
      await navigator.clipboard.writeText(text);
      const old = button.textContent;
      button.textContent = 'Copiado';
      setTimeout(() => { button.textContent = old; }, 1600);
    } catch (_) {
      const area = document.createElement('textarea');
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
  }

  function ensureOutput(panel) {
    let box = panel.querySelector('#investia-homologation-output');
    if (box) return box;

    box = document.createElement('article');
    box.id = 'investia-homologation-output';
    box.className = 'panel';
    box.style.marginTop = '18px';
    box.style.display = 'none';
    box.innerHTML = `
      <div class="panel-title">
        <div><span class="eyebrow">HOMOLOGAÇÃO</span><h3>Dados para teste</h3></div>
        <div class="investia-actions">
          <button class="ghost" type="button" id="investia-homologation-copy">Copiar</button>
          <button class="ghost" type="button" id="investia-homologation-close">Fechar</button>
        </div>
      </div>
      <pre id="investia-homologation-text" class="investia-result" style="max-height:55vh;overflow:auto"></pre>
    `;
    panel.appendChild(box);
    box.querySelector('#investia-homologation-close').addEventListener('click', () => { box.style.display = 'none'; });
    box.querySelector('#investia-homologation-copy').addEventListener('click', event => {
      copyText(box.querySelector('#investia-homologation-text').textContent, event.currentTarget);
    });
    return box;
  }

  function install() {
    const panel = document.getElementById(PANEL_ID);
    if (!panel || panel.dataset.homologationButton === '1') return false;

    const refresh = panel.querySelector('#investia-refresh');
    if (!refresh) return false;

    const button = document.createElement('button');
    button.className = 'primary';
    button.type = 'button';
    button.id = 'investia-generate-homologation';
    button.textContent = 'Gerar homologação';
    refresh.parentNode.insertBefore(button, refresh);

    button.addEventListener('click', () => {
      const form = panel.querySelector('#investia-project-form');
      if (!form || !panel.querySelector('#investia-title')?.textContent?.trim()) return;
      const text = buildHomologationText();
      const box = ensureOutput(panel);
      box.querySelector('#investia-homologation-text').textContent = text;
      box.style.display = 'block';
      box.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    panel.dataset.homologationButton = '1';
    return true;
  }

  if (!install()) {
    const observer = new MutationObserver(() => {
      if (install()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
})();
