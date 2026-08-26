(() => {
  'use strict';

  if (window.__devpilotGameRulesAdminReady) return;
  window.__devpilotGameRulesAdminReady = true;

  const stateRules = {rules: [], selectedId: ''};
  const isSuperAdmin = () => String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase() === 'SUPER_ADMIN';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[char]);

  function ensureStyle() {
    if (document.getElementById('game-rules-admin-style')) return;
    const style = document.createElement('style');
    style.id = 'game-rules-admin-style';
    style.textContent = `
      .game-rules-grid{display:grid;grid-template-columns:minmax(220px,.72fr) minmax(0,1.5fr);gap:16px;align-items:start}
      .game-rule-list{display:grid;gap:8px;max-height:72vh;overflow:auto}.game-rule-item{width:100%;text-align:left;padding:12px;border:1px solid var(--border,#26354a);border-radius:12px;background:transparent;color:inherit}.game-rule-item.active{border-color:#5bdfff}.game-rule-item small{display:block;opacity:.72;margin-top:3px}
      .game-rule-form{display:grid;gap:12px}.game-rule-form textarea{min-height:120px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}.game-rule-actions{display:flex;gap:8px;flex-wrap:wrap}.game-rule-result{white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;border:1px solid var(--border,#26354a);border-radius:12px;background:rgba(0,0,0,.18);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
      @media(max-width:800px){.game-rules-grid{grid-template-columns:1fr}.game-rule-actions>*{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function parseJson(text, fallback) {
    const raw = String(text || '').trim();
    if (!raw) return fallback;
    const value = JSON.parse(raw);
    return value;
  }

  function selectedRule() {
    return stateRules.rules.find(rule => rule.id === stateRules.selectedId) || null;
  }

  function openView(button, section) {
    if (!isSuperAdmin()) return toast?.('Acesso exclusivo do Super Admin');
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Regras do Jogo';
    void loadRules();
  }

  function ensurePanel() {
    if (!isSuperAdmin() || document.getElementById('game-rules-admin-view')) return;
    ensureStyle();
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;

    const button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.view = 'game-rules-admin';
    button.textContent = 'Regras do Jogo';
    nav.insertBefore(button, nav.querySelector('[data-view="reports"]') || null);

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'game-rules-admin-view';
    section.innerHTML = `
      <div class="section-head"><div><span class="eyebrow">SUPER ADMIN · GAME ENGINE</span><h2>Regras do Jogo</h2><p>Crie regras declarativas, simule com dry-run e publique versões imutáveis sem alterar código.</p></div><button class="ghost" type="button" id="game-rule-new">+ Nova regra</button></div>
      <div class="game-rules-grid">
        <article class="panel"><div class="panel-title"><div><span class="eyebrow">VERSÕES</span><h3>Regras cadastradas</h3></div><button class="link" id="game-rules-refresh" type="button">Atualizar</button></div><div id="game-rule-list" class="game-rule-list"></div></article>
        <div style="display:grid;gap:16px">
          <article class="panel">
            <form id="game-rule-form" class="game-rule-form">
              <input type="hidden" name="id">
              <div class="form-grid"><label>Chave da regra<input name="rule_key" placeholder="task-security-reward" required></label><label>Evento<input name="event_type" placeholder="task.completed" required></label></div>
              <div class="form-grid"><label>Nome<input name="name" required></label><label>Prioridade<input name="priority" type="number" min="0" max="10000" value="100"></label></div>
              <label>Descrição<textarea name="description" rows="2"></textarea></label>
              <label>Condições JSON<textarea name="conditions" spellcheck="false">[{"field":"task.category","operator":"eq","value":"security"}]</textarea></label>
              <label>Ações JSON<textarea name="actions" spellcheck="false">[{"type":"award_xp","amount":5}]</textarea></label>
              <div class="game-rule-actions"><button class="primary" type="submit">Salvar rascunho</button><button class="ghost" type="button" id="game-rule-publish">Publicar versão</button></div>
              <small id="game-rule-status" class="hint">Rascunhos podem ser alterados. Publicados são imutáveis.</small>
            </form>
          </article>
          <article class="panel"><div class="panel-title"><div><span class="eyebrow">DRY-RUN</span><h3>Simular evento</h3></div></div><form id="game-rule-sim-form" class="game-rule-form"><label>Tipo do evento<input name="event_type" value="task.completed" required></label><label>Evento JSON<textarea name="event" spellcheck="false">{"task":{"category":"security","status":"completed"}}</textarea></label><label class="check"><input name="use_draft" type="checkbox" checked> Simular somente o rascunho selecionado</label><button class="ghost" type="submit">Simular sem efeitos</button></form><div id="game-rule-sim-result" class="game-rule-result" style="margin-top:12px">Nenhuma simulação executada.</div></article>
        </div>
      </div>`;
    const anchor = document.getElementById('reports-view');
    (anchor?.parentNode || main).insertBefore(section, anchor || null);
    button.addEventListener('click', () => openView(button, section));
    section.querySelector('#game-rules-refresh').addEventListener('click', loadRules);
    section.querySelector('#game-rule-new').addEventListener('click', resetForm);
    section.querySelector('#game-rule-form').addEventListener('submit', saveRule);
    section.querySelector('#game-rule-publish').addEventListener('click', publishRule);
    section.querySelector('#game-rule-sim-form').addEventListener('submit', simulateRule);
  }

  function renderList() {
    const target = document.getElementById('game-rule-list');
    if (!target) return;
    target.innerHTML = stateRules.rules.map(rule => `<button type="button" class="game-rule-item ${rule.id === stateRules.selectedId ? 'active' : ''}" data-id="${esc(rule.id)}"><strong>${esc(rule.name)}</strong><small>${esc(rule.rule_key)} · v${rule.version} · ${esc(rule.status)}</small><small>${esc(rule.event_type)} · prioridade ${rule.priority}</small></button>`).join('') || '<div class="empty">Nenhuma regra cadastrada.</div>';
    target.querySelectorAll('[data-id]').forEach(button => button.addEventListener('click', () => {stateRules.selectedId = button.dataset.id; renderList(); fillForm();}));
  }

  function fillForm() {
    const rule = selectedRule();
    const form = document.getElementById('game-rule-form');
    if (!rule || !form) return resetForm();
    form.elements.id.value = rule.id;
    form.elements.rule_key.value = rule.rule_key;
    form.elements.rule_key.disabled = true;
    form.elements.name.value = rule.name || '';
    form.elements.description.value = rule.description || '';
    form.elements.event_type.value = rule.event_type || '';
    form.elements.priority.value = rule.priority ?? 100;
    form.elements.conditions.value = JSON.stringify(rule.conditions || [], null, 2);
    form.elements.actions.value = JSON.stringify(rule.actions || [], null, 2);
    const immutable = rule.status !== 'draft';
    [...form.elements].forEach(element => { if (!['id','rule_key'].includes(element.name) && element.id !== 'game-rule-publish') element.disabled = immutable; });
    document.getElementById('game-rule-publish').disabled = immutable;
    document.getElementById('game-rule-status').textContent = `Versão ${rule.version} · ${String(rule.status).toUpperCase()}${immutable ? ' · imutável' : ''}`;
  }

  function resetForm() {
    stateRules.selectedId = '';
    renderList();
    const form = document.getElementById('game-rule-form');
    if (!form) return;
    form.reset();
    form.elements.id.value = '';
    form.elements.rule_key.disabled = false;
    form.elements.priority.value = 100;
    form.elements.conditions.value = '[{"field":"task.category","operator":"eq","value":"security"}]';
    form.elements.actions.value = '[{"type":"award_xp","amount":5}]';
    [...form.elements].forEach(element => element.disabled = false);
    document.getElementById('game-rule-publish').disabled = true;
    document.getElementById('game-rule-status').textContent = 'Nova versão em rascunho.';
  }

  async function loadRules() {
    if (!isSuperAdmin()) return;
    try {
      stateRules.rules = await api('/game/rules');
      if (stateRules.selectedId && !stateRules.rules.some(rule => rule.id === stateRules.selectedId)) stateRules.selectedId = '';
      renderList();
      if (stateRules.selectedId) fillForm();
    } catch (error) { toast?.(error?.message || 'Falha ao carregar regras do jogo.'); }
  }

  async function saveRule(event) {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const conditions = parseJson(form.elements.conditions.value, []);
      const actions = parseJson(form.elements.actions.value, []);
      const id = form.elements.id.value;
      const body = {name: form.elements.name.value, description: form.elements.description.value, event_type: form.elements.event_type.value, priority: Number(form.elements.priority.value || 100), conditions, actions};
      let rule;
      if (id) rule = await api(`/game/rules/${encodeURIComponent(id)}`, {method:'PATCH', body:JSON.stringify(body)});
      else rule = await api('/game/rules', {method:'POST', body:JSON.stringify({...body, rule_key: form.elements.rule_key.value})});
      stateRules.selectedId = rule.id;
      toast?.('Rascunho salvo.');
      await loadRules();
      fillForm();
    } catch (error) { toast?.(error?.message || 'Regra inválida. Verifique os JSONs.'); }
  }

  async function publishRule() {
    const rule = selectedRule();
    if (!rule || rule.status !== 'draft') return;
    if (!window.confirm('Publicar esta versão? Ela ficará imutável e substituirá a versão publicada anterior desta chave.')) return;
    try { await api(`/game/rules/${encodeURIComponent(rule.id)}/publish`, {method:'POST'}); toast?.('Regra publicada.'); await loadRules(); fillForm(); }
    catch (error) { toast?.(error?.message || 'Falha ao publicar regra.'); }
  }

  async function simulateRule(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const target = document.getElementById('game-rule-sim-result');
    try {
      const payload = {event_type: form.elements.event_type.value, event: parseJson(form.elements.event.value, {})};
      const selected = selectedRule();
      if (form.elements.use_draft.checked && selected?.status === 'draft') payload.draft_rule_id = selected.id;
      const result = await api('/game/rules/simulate', {method:'POST', body:JSON.stringify(payload)});
      target.textContent = JSON.stringify(result, null, 2);
    } catch (error) { target.textContent = error?.message || 'Falha na simulação.'; }
  }

  const boot = () => { ensurePanel(); window.setTimeout(ensurePanel, 500); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true}); else boot();
})();
