(() => {
  if (window.__devpilotMentorSecurityLoaded) return;
  window.__devpilotMentorSecurityLoaded = true;

  const modal = document.createElement('dialog');
  modal.id = 'mentor-security-modal';
  modal.className = 'mentor-security-modal';
  modal.innerHTML = `
    <form method="dialog" class="mentor-security-shell">
      <header>
        <div><span class="eyebrow">DEVPILOT</span><h2>Mentor & Segurança</h2></div>
        <button class="link" value="cancel" aria-label="Fechar">Fechar</button>
      </header>
      <div class="mentor-security-tabs" role="tablist">
        <button type="button" class="primary" data-ms-tab="mentor">Mentor</button>
        <button type="button" class="link" data-ms-tab="security">Segurança</button>
      </div>
      <section data-ms-panel="mentor">
        <p class="mentor-security-help">Aprenda usando o código real do projeto. Explicar, Ensinar, Fazer comigo e Quiz são somente leitura. Executar sempre gera tarefa sujeita à aprovação.</p>
        <label>Modo<select id="ms-mode"><option value="explain">Explicar</option><option value="teach">Ensinar</option><option value="pair">Fazer comigo</option><option value="quiz">Testar conhecimento</option><option value="execute">Executar</option></select></label>
        <label>O que você quer entender ou fazer?<textarea id="ms-question" rows="5" maxlength="6000" placeholder="Ex.: explique por que esta rota exige aprovação e como eu valido isso"></textarea></label>
        <div class="mentor-security-grid">
          <label>Arquivo alvo (opcional)<input id="ms-target" maxlength="500" placeholder="app/security.py"></label>
          <label>Competência (opcional)<input id="ms-skill" maxlength="120" placeholder="FastAPI, Docker, RBAC..."></label>
          <label>Nível<select id="ms-level"><option value="">Automático</option><option value="beginner">Iniciante</option><option value="intermediate">Intermediário</option><option value="advanced">Avançado</option><option value="expert">Especialista</option></select></label>
        </div>
        <button type="button" class="primary" id="ms-submit">Iniciar</button>
        <div class="mentor-security-output" id="ms-mentor-output"></div>
      </section>
      <section data-ms-panel="security" hidden>
        <p class="mentor-security-help">A varredura é local e determinística. Ela não envia o repositório para IA. Correções só viram tarefas após sua confirmação e continuam aguardando aprovação.</p>
        <div class="mentor-security-actions"><button type="button" class="primary" id="ms-scan">Verificar segurança</button><button type="button" class="link" id="ms-refresh-security">Atualizar achados</button></div>
        <div class="mentor-security-output" id="ms-security-output"></div>
      </section>
    </form>`;
  document.body.appendChild(modal);

  let currentProjectId = '';
  let currentProjectName = '';

  const output = id => document.getElementById(id);
  const message = (id, text, kind = '') => {
    const target = output(id);
    if (!target) return;
    target.innerHTML = `<div class="mentor-security-message ${kind}">${esc(text)}</div>`;
  };

  const switchTab = name => {
    modal.querySelectorAll('[data-ms-panel]').forEach(node => { node.hidden = node.dataset.msPanel !== name; });
    modal.querySelectorAll('[data-ms-tab]').forEach(node => {
      node.className = node.dataset.msTab === name ? 'primary' : 'link';
    });
  };
  modal.querySelectorAll('[data-ms-tab]').forEach(button => { button.onclick = () => switchTab(button.dataset.msTab); });

  const findingCard = finding => `
    <article class="mentor-security-finding severity-${esc(finding.severity)}">
      <div class="mentor-security-finding-head"><strong>${esc(finding.title)}</strong><span>${esc(finding.severity.toUpperCase())}</span></div>
      <small>${esc(finding.rule_id)} · ${esc(finding.file_path || 'projeto')}${finding.line_number ? ':' + Number(finding.line_number) : ''}</small>
      <p>${esc(finding.impact)}</p>
      <details><summary>Como corrigir</summary><p>${esc(finding.remediation)}</p><code>${esc(finding.evidence || 'evidência não exibida')}</code></details>
      <button type="button" class="link ms-fix" data-finding="${esc(finding.id)}">Criar tarefa de correção</button>
    </article>`;

  async function loadFindings() {
    if (!currentProjectId) return;
    message('ms-security-output', 'Carregando achados…');
    try {
      const findings = await api(`/projects/${currentProjectId}/security/findings?status=open`);
      output('ms-security-output').innerHTML = findings.length
        ? findings.map(findingCard).join('')
        : '<div class="mentor-security-message ok">Nenhum achado aberto registrado.</div>';
      modal.querySelectorAll('.ms-fix').forEach(button => {
        button.onclick = async () => {
          const finding = findings.find(item => item.id === button.dataset.finding);
          if (!finding) return;
          const confirmed = window.confirm(`Criar uma tarefa para corrigir ${finding.rule_id} — ${finding.title}? A tarefa ainda exigirá aprovação antes de executar.`);
          if (!confirmed) return;
          button.disabled = true;
          try {
            const result = await api(`/projects/${currentProjectId}/security/findings/${finding.id}/fix`, {
              method: 'POST', body: JSON.stringify({apply: true}),
            });
            toast(result.message || 'Tarefa de correção criada');
            await load();
          } catch (error) {
            toast(error.message);
          } finally {
            button.disabled = false;
          }
        };
      });
    } catch (error) {
      message('ms-security-output', error.message, 'error');
    }
  }

  document.getElementById('ms-scan').onclick = async event => {
    if (!currentProjectId) return;
    const button = event.currentTarget;
    button.disabled = true;
    message('ms-security-output', 'Verificando código, configuração, containers e CI/CD…');
    try {
      const result = await api(`/projects/${currentProjectId}/security/scan`, {method: 'POST'});
      const scan = result.scan;
      toast(`Segurança verificada: ${scan.critical_count} crítico(s), ${scan.high_count} alto(s)`);
      await loadFindings();
    } catch (error) {
      message('ms-security-output', error.message, 'error');
    } finally {
      button.disabled = false;
    }
  };
  document.getElementById('ms-refresh-security').onclick = loadFindings;

  document.getElementById('ms-submit').onclick = async event => {
    if (!currentProjectId) return;
    const button = event.currentTarget;
    const mode = document.getElementById('ms-mode').value;
    const question = document.getElementById('ms-question').value.trim();
    if (!question) return toast('Descreva o que você quer entender ou fazer');
    const payload = {
      mode,
      question,
      target: document.getElementById('ms-target').value.trim() || null,
      skill: document.getElementById('ms-skill').value.trim() || null,
      level: document.getElementById('ms-level').value || null,
    };
    if (mode === 'execute') {
      const confirmed = window.confirm('Executar cria uma tarefa que pode alterar código. Ela ficará aguardando aprovação explícita. Continuar?');
      if (!confirmed) return;
    }
    button.disabled = true;
    message('ms-mentor-output', 'Preparando contexto seguro do projeto…');
    try {
      const result = await api(`/projects/${currentProjectId}/mentor`, {method: 'POST', body: JSON.stringify(payload)});
      message('ms-mentor-output', result.message || 'Solicitação registrada.', 'ok');
      toast(result.message || 'Mentor iniciado');
      await load();
    } catch (error) {
      message('ms-mentor-output', error.message, 'error');
    } finally {
      button.disabled = false;
    }
  };

  function openPanel(projectId, projectName, tab = 'mentor') {
    currentProjectId = projectId;
    currentProjectName = projectName || 'Projeto';
    modal.querySelector('h2').textContent = `Mentor & Segurança · ${currentProjectName}`;
    switchTab(tab);
    modal.showModal();
    if (tab === 'security') loadFindings();
  }

  function injectProjectActions() {
    const list = document.getElementById('projects-list');
    if (!list || !Array.isArray(state?.projects)) return;
    const cards = [...list.querySelectorAll('.project-card')];
    cards.forEach((card, index) => {
      const project = state.projects[index];
      if (!project || card.dataset.mentorSecurity === '1') return;
      card.dataset.mentorSecurity = '1';
      const row = card.querySelector('.list-row > div') || card.querySelector('.list-row');
      if (!row) return;
      const mentor = document.createElement('button');
      mentor.type = 'button'; mentor.className = 'link'; mentor.textContent = 'Mentor';
      mentor.onclick = () => openPanel(project.id, project.name, 'mentor');
      const security = document.createElement('button');
      security.type = 'button'; security.className = 'link'; security.textContent = 'Segurança';
      security.onclick = () => openPanel(project.id, project.name, 'security');
      row.append(mentor, security);
    });
  }

  if (typeof renderProjects === 'function') {
    const originalRenderProjects = renderProjects;
    renderProjects = function mentorSecurityRenderProjects(...args) {
      const value = originalRenderProjects.apply(this, args);
      injectProjectActions();
      return value;
    };
  }
  window.setTimeout(injectProjectActions, 0);
})();
