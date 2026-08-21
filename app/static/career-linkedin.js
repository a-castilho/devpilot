(() => {
  if (document.querySelector('[data-view="career"]')) return;

  const style = document.createElement('style');
  style.textContent = `
    #career-view .career-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:18px}
    #career-view .career-card{background:var(--panel,#0d1a2b);border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:18px}
    #career-view .career-card h3{margin:4px 0 10px} #career-view .career-card p{line-height:1.55}
    #career-view .career-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
    #career-view .career-upload{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
    #career-view .career-json{width:100%;min-height:220px;font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
    #career-view .career-value{white-space:pre-wrap;overflow-wrap:anywhere;background:rgba(255,255,255,.035);padding:12px;border-radius:12px}
    #career-view .career-skills{display:flex;gap:7px;flex-wrap:wrap}
    #career-view .career-skill{padding:5px 9px;border-radius:999px;background:rgba(255,255,255,.07);font-size:12px}
    #career-view .career-change{padding:10px 0;border-bottom:1px solid rgba(255,255,255,.07)}
    #career-view .career-change:last-child{border-bottom:0} #career-view .career-change strong{display:block;text-transform:uppercase;font-size:11px;letter-spacing:.08em;margin-bottom:4px}
    #career-view .career-note{font-size:12px;opacity:.75} #career-view .career-status{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
    @media(max-width:900px){#career-view .career-grid{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const nav = document.querySelector('.sidebar nav');
  const button = document.createElement('button');
  button.className = 'nav';
  button.type = 'button';
  button.dataset.view = 'career';
  button.textContent = 'Career / LinkedIn';
  const audit = nav?.querySelector('[data-view="audit"]');
  nav?.insertBefore(button, audit || null);

  const view = document.createElement('section');
  view.className = 'view';
  view.id = 'career-view';
  view.innerHTML = `
    <div class="section-head"><div><p>Currículo como fonte de verdade, diff e aprovação antes da sincronização.</p></div></div>
    <div class="career-grid">
      <div>
        <article class="career-card">
          <span class="eyebrow">CURRÍCULO → PERFIL CANÔNICO</span><h3>Importar currículo</h3>
          <p>Suporta DOCX, TXT e Markdown.</p>
          <form id="career-upload-form" class="career-upload"><input id="career-file" type="file" accept=".docx,.txt,.md" required><button class="primary" type="submit">Importar e comparar</button></form>
          <p class="career-note" id="career-source">Nenhum currículo importado.</p>
        </article>
        <article class="career-card" style="margin-top:18px">
          <span class="eyebrow">PREVIEW DO LINKEDIN</span><h3 id="career-headline">Sem perfil carregado</h3>
          <div class="career-value" id="career-about">Importe um currículo para gerar o conteúdo.</div>
          <h4>Competências</h4><div class="career-skills" id="career-skills"></div>
          <h4>Experiência</h4><div id="career-experience"></div>
          <h4>Projetos</h4><div id="career-projects"></div>
        </article>
      </div>
      <div>
        <article class="career-card">
          <span class="eyebrow">ESTADO ATUAL DO LINKEDIN</span><h3>Baseline para comparação</h3>
          <p>Cole um JSON do perfil atual. Vazio significa primeira sincronização.</p>
          <textarea class="career-json" id="career-baseline" spellcheck="false" placeholder='{"headline":"...","about":"...","skills":[]}'></textarea>
          <div class="career-actions"><button class="ghost" type="button" id="career-save-baseline">Salvar baseline</button><button class="ghost" type="button" id="career-clear-baseline">Baseline vazio</button></div>
        </article>
        <article class="career-card" style="margin-top:18px">
          <span class="eyebrow">ALTERAÇÕES DETECTADAS</span>
          <div class="career-status"><h3 style="margin-right:auto">Diff</h3><span class="status" id="career-approval-status">não aprovado</span></div>
          <div id="career-changes"><div class="empty">Nenhuma comparação disponível.</div></div>
          <div class="career-actions"><button class="primary" type="button" id="career-approve">Aprovar alterações</button><button class="ghost" type="button" id="career-export">Exportar pacote JSON</button></div>
          <p class="career-note" id="career-linkedin-mode">Publicação direta exige acesso aprovado à API oficial do LinkedIn.</p>
        </article>
      </div>
    </div>`;
  document.querySelector('main')?.appendChild(view);

  let careerState = null;
  const stringify = value => JSON.stringify(value ?? {}, null, 2);
  const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
  const isNetworkError = error => {
    const message = String(error?.message || error || '');
    return error instanceof TypeError || /failed to fetch|networkerror|network request failed|load failed/i.test(message);
  };

  async function waitForApi(timeoutMs = 7000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      try {
        const response = await fetch('/health', {
          cache: 'no-store',
          credentials: 'same-origin',
          headers: {'Cache-Control': 'no-cache'},
        });
        if (response.ok) return true;
      } catch (_) {
        // The app container can be restarting; keep polling until the short deadline.
      }
      await wait(450);
    }
    return false;
  }

  async function careerApi(path, options = {}, retries = 1) {
    let lastError = null;
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      try {
        return await api(path, options);
      } catch (error) {
        lastError = error;
        if (!isNetworkError(error)) throw error;
        if (attempt >= retries) break;
        toast('Conexão com a API interrompida. Reconectando…');
        const online = await waitForApi();
        if (!online) break;
      }
    }
    throw new Error(`API do DevPilot indisponível em ${window.location.host}. Aguarde alguns segundos e tente novamente.`);
  }

  async function importCareerFile(file, body) {
    try {
      return await api('/career/cv/import', {method:'POST', body});
    } catch (error) {
      if (!isNetworkError(error)) throw error;
      toast('Upload interrompido. Reconectando ao DevPilot…');
      if (!await waitForApi()) {
        throw new Error(`API do DevPilot indisponível em ${window.location.host}.`);
      }

      // If the request reached the server but the response was lost, recover the
      // already imported state instead of sending the same file twice.
      try {
        const current = await api('/career');
        if (current?.profile && current?.source_filename === file.name) return current;
      } catch (recoveryError) {
        if (!isNetworkError(recoveryError)) throw recoveryError;
      }

      return careerApi('/career/cv/import', {method:'POST', body}, 1);
    }
  }

  const renderList = (target, items, formatter) => {
    target.innerHTML = items?.length ? items.map(formatter).join('') : '<div class="empty">Nenhum item identificado.</div>';
  };

  function render(data) {
    careerState = data;
    const profile = data?.profile || {};
    document.querySelector('#career-source').textContent = data?.source_filename
      ? `${data.source_filename} · SHA ${String(data.source_sha256 || '').slice(0, 12)} · ${new Date(data.updated_at).toLocaleString('pt-BR')}`
      : 'Nenhum currículo importado.';
    document.querySelector('#career-headline').textContent = profile.headline || 'Sem headline';
    document.querySelector('#career-about').textContent = profile.about || 'Sem resumo profissional identificado.';
    renderList(document.querySelector('#career-skills'), profile.skills || [], item => `<span class="career-skill">${esc(item)}</span>`);
    renderList(document.querySelector('#career-experience'), profile.experience || [], item => `<div class="career-change"><strong>${esc(item.company || '')} · ${esc(item.period || '')}</strong><b>${esc(item.title || '')}</b><p>${esc(item.description || '')}</p></div>`);
    renderList(document.querySelector('#career-projects'), profile.projects || [], item => `<div class="career-change"><strong>${esc(item.name || '')}</strong><p>${esc(item.description || '')}</p></div>`);
    document.querySelector('#career-baseline').value = stringify(data?.linkedin_baseline || {});
    const changes = data?.changes || [];
    document.querySelector('#career-changes').innerHTML = changes.length
      ? changes.map(change => `<div class="career-change"><strong>${esc(change.field)}</strong><span>alteração detectada</span></div>`).join('')
      : '<div class="empty">Nenhuma alteração detectada.</div>';
    const approval = document.querySelector('#career-approval-status');
    approval.textContent = data?.approved ? 'aprovado' : 'não aprovado';
    approval.className = `status ${data?.approved ? 'completed' : 'awaiting_approval'}`;
    document.querySelector('#career-linkedin-mode').textContent = data?.linkedin?.reason || 'Publicação direta exige acesso aprovado à API oficial do LinkedIn.';
    document.querySelector('#career-approve').disabled = !profile.headline;
    document.querySelector('#career-export').disabled = !data?.approved;
  }

  async function loadCareer() {
    try { render(await careerApi('/career', {}, 2)); } catch (error) { toast(error.message); }
  }

  button.onclick = () => {
    document.querySelectorAll('.view').forEach(node => node.classList.toggle('active', node === view));
    document.querySelectorAll('.nav').forEach(node => node.classList.toggle('active', node === button));
    const title = document.querySelector('#page-title'); if (title) title.textContent = 'Career / LinkedIn Sync';
    loadCareer();
  };

  document.querySelector('#career-upload-form').onsubmit = async event => {
    event.preventDefault();
    const file = document.querySelector('#career-file').files?.[0];
    if (!file) return toast('Selecione um currículo');
    const body = new FormData(); body.append('file', file);
    const submit = event.currentTarget.querySelector('button[type="submit"]');
    const originalLabel = submit?.textContent || 'Importar e comparar';
    if (submit) { submit.disabled = true; submit.textContent = 'Importando…'; }
    document.querySelector('#career-source').textContent = `Enviando ${file.name}…`;
    try {
      render(await importCareerFile(file, body));
      toast('Currículo importado e diff recalculado');
    } catch (error) {
      toast(error.message);
      if (careerState) render(careerState);
      else document.querySelector('#career-source').textContent = 'Falha no envio. Tente novamente.';
    } finally {
      if (submit) { submit.disabled = false; submit.textContent = originalLabel; }
    }
  };

  document.querySelector('#career-save-baseline').onclick = async () => {
    try {
      const baseline = JSON.parse(document.querySelector('#career-baseline').value || '{}');
      render(await careerApi('/career/linkedin/baseline', {method:'PUT', body:JSON.stringify(baseline)})); toast('Baseline salvo');
    } catch (error) { toast(error instanceof SyntaxError ? 'JSON do baseline inválido' : error.message); }
  };

  document.querySelector('#career-clear-baseline').onclick = async () => {
    const empty = {headline:'',about:'',experience:[],skills:[],projects:[],education:[],languages:[]};
    try { render(await careerApi('/career/linkedin/baseline', {method:'PUT', body:JSON.stringify(empty)})); toast('Baseline limpo'); } catch (error) { toast(error.message); }
  };

  document.querySelector('#career-approve').onclick = async () => {
    if (!careerState?.source_sha256) return toast('Importe um currículo primeiro');
    try {
      render(await careerApi('/career/linkedin/approve', {method:'POST', body:JSON.stringify({expected_source_sha256:careerState.source_sha256})}));
      toast('Alterações aprovadas para sincronização');
    } catch (error) { toast(error.message); }
  };

  document.querySelector('#career-export').onclick = async () => {
    try {
      const payload = await careerApi('/career/linkedin/export', {}, 2);
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type:'application/json'});
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = `linkedin-sync-${new Date().toISOString().slice(0,10)}.json`; link.click(); URL.revokeObjectURL(url);
      toast('Pacote aprovado exportado');
    } catch (error) { toast(error.message); }
  };
})();
