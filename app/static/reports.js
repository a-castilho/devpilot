(() => {
  const nav = document.querySelector('[data-view="reports"]');
  const view = document.querySelector('#reports-view');
  if (!nav || !view) return;

  let report = null;
  let selected = null;
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  function markdown(content) {
    let inCode = false;
    return String(content || '').split('\n').map(line => {
      if (line.trim().startsWith('```')) { inCode = !inCode; return inCode ? '<pre><code>' : '</code></pre>'; }
      if (inCode) return `${esc(line)}\n`;
      if (line.startsWith('### ')) return `<h4>${esc(line.slice(4))}</h4>`;
      if (line.startsWith('## ')) return `<h3>${esc(line.slice(3))}</h3>`;
      if (line.startsWith('# ')) return `<h2>${esc(line.slice(2))}</h2>`;
      if (/^[-*] /.test(line)) return `<div class="report-bullet"><span>•</span><p>${esc(line.slice(2))}</p></div>`;
      if (!line.trim()) return '';
      return `<p>${esc(line)}</p>`;
    }).join('');
  }

  function documents() {
    const q = (document.querySelector('#report-search')?.value || '').trim().toLowerCase();
    const category = document.querySelector('#report-category')?.value || 'Todos';
    return (report?.documents || []).filter(item => (category === 'Todos' || item.category === category) && (!q || `${item.title} ${item.source} ${item.content}`.toLowerCase().includes(q)));
  }

  function renderList() {
    const list = document.querySelector('#report-list');
    const docs = documents();
    if (!docs.some(item => item.id === selected)) selected = docs[0]?.id || null;
    list.innerHTML = docs.map(item => `<button class="report-item ${item.id === selected ? 'active' : ''}" data-report-id="${esc(item.id)}"><span>${esc(item.category)}</span><strong>${esc(item.title)}</strong><small>${esc(item.source)}</small></button>`).join('') || '<div class="empty">Nenhum documento encontrado.</div>';
    list.querySelectorAll('[data-report-id]').forEach(button => button.onclick = () => { selected = button.dataset.reportId; renderList(); renderReader(); });
    renderReader();
  }

  function renderReader() {
    const item = (report?.documents || []).find(doc => doc.id === selected);
    const target = document.querySelector('#report-reader');
    if (!item) { target.innerHTML = '<div class="empty">Selecione um documento.</div>'; return; }
    target.innerHTML = `<div class="report-reader-head"><div><span>${esc(item.category)}</span><h2>${esc(item.title)}</h2></div><code>${esc(item.source)}</code></div><div class="report-markdown">${markdown(item.content)}</div>`;
  }

  async function loadReports() {
    try {
      report = await api('/project-report');
      const categories = ['Todos', ...new Set((report.documents || []).map(item => item.category).filter(Boolean))];
      document.querySelector('#report-category').innerHTML = categories.map(item => `<option>${esc(item)}</option>`).join('');
      document.querySelector('#report-privacy').textContent = report.privacy?.notice || 'Conteúdo sanitizado.';
      selected = report.documents?.[0]?.id || null;
      renderList();
    } catch (error) {
      document.querySelector('#report-reader').innerHTML = `<div class="empty">${esc(error.message)}</div>`;
    }
  }

  nav.addEventListener('click', () => {
    document.querySelectorAll('.view').forEach(item => item.classList.toggle('active', item === view));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === nav));
    document.querySelector('#page-title').textContent = 'Relatórios';
    loadReports();
  });
  document.querySelector('#report-search').addEventListener('input', renderList);
  document.querySelector('#report-category').addEventListener('change', renderList);
  document.querySelector('#report-copy').onclick = async () => {
    const item = (report?.documents || []).find(doc => doc.id === selected);
    if (!item) return;
    await navigator.clipboard.writeText(`[DevPilot · ${item.category}] ${item.title}\nFonte: ${item.source}\n\n${item.content}`);
    document.querySelector('#report-copy').textContent = 'Copiado';
    setTimeout(() => document.querySelector('#report-copy').textContent = 'Copiar para conversa', 1600);
  };
  document.querySelector('#report-new-idea').onclick = () => window.open('https://github.com/a-castilho/devpilot/issues/new?template=idea.yml', '_blank', 'noopener,noreferrer');
})();
