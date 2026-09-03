(() => {
  'use strict';

  if (window.__devpilotProjectBuilderMobileRuntimeV39) return;
  window.__devpilotProjectBuilderMobileRuntimeV39 = true;

  const isMobile = () => window.matchMedia?.('(max-width: 900px)')?.matches === true;
  if (!isMobile()) return;

  const form = document.querySelector('#project-builder-form');
  const host = document.querySelector('#project-builder-groups');
  if (!form || !host) return;

  const STYLE_ID = 'devpilot-project-builder-mobile-runtime-v39-style';
  let installed = false;
  let activeKey = '';
  let records = [];
  let observer = null;
  let compactTimer = 0;

  function installStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      @media (max-width:900px) {
        html[data-devpilot-view="new-project"] body .voice-dock {display:none!important}
        html[data-devpilot-view="new-project"] body .sidebar {
          backdrop-filter:none!important;
          -webkit-backdrop-filter:none!important;
          box-shadow:none!important;
          background:#081321!important;
        }
        #project-builder-form[data-mobile-virtualized="1"] .builder-mobile-v39-toggle {
          flex:0 0 auto!important;
          min-height:38px!important;
          padding:7px 11px!important;
          border:1px solid rgba(55,215,255,.24)!important;
          border-radius:10px!important;
          background:#0b1a29!important;
          color:#dff8ff!important;
          font-size:13px!important;
          font-weight:800!important;
        }
        #project-builder-form[data-mobile-virtualized="1"] .builder-mobile-v39-state {
          display:block!important;
          flex:1 0 100%!important;
          margin-top:3px!important;
          color:var(--muted,#8fa3bf)!important;
          font-size:12px!important;
          line-height:1.35!important;
        }
        #project-builder-form[data-mobile-virtualized="1"] .builder-group-head {
          align-items:center!important;
          flex-wrap:wrap!important;
          gap:8px!important;
        }
        #project-builder-form[data-mobile-virtualized="1"] .choice-strip[data-mobile-v39-closed="1"] {
          display:none!important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function selectedLabels(record) {
    return record.nodes
      .filter(node => node.classList?.contains('selected'))
      .map(node => String(node.querySelector?.('strong')?.textContent || '').trim())
      .filter(Boolean);
  }

  function refreshState(record) {
    const labels = selectedLabels(record);
    if (!record.state) return;
    record.state.textContent = labels.length
      ? `${labels.length} selecionada${labels.length === 1 ? '' : 's'}: ${labels.slice(0, 2).join(', ')}${labels.length > 2 ? '…' : ''}`
      : 'Nenhuma opção selecionada';
  }

  function mountAll(record) {
    record.strip.replaceChildren(...record.nodes);
  }

  function compactRecord(record) {
    if (!record?.strip) return;
    const cache = document.createDocumentFragment();
    record.nodes.forEach(node => {
      if (!node.classList?.contains('selected')) cache.appendChild(node);
    });
    record.cache = cache;
    record.strip.style.setProperty('display', 'none', 'important');
    record.strip.dataset.mobileV39Closed = '1';
    record.strip.setAttribute('aria-hidden', 'true');
    record.toggle?.setAttribute('aria-expanded', 'false');
    if (record.toggle) record.toggle.textContent = 'Configurar';
    refreshState(record);
  }

  function expandRecord(record) {
    if (!record?.strip) return;
    records.forEach(other => {
      if (other !== record) compactRecord(other);
    });
    mountAll(record);
    record.strip.style.removeProperty('display');
    record.strip.dataset.mobileV39Closed = '0';
    record.strip.removeAttribute('aria-hidden');
    record.toggle?.setAttribute('aria-expanded', 'true');
    if (record.toggle) record.toggle.textContent = 'Fechar';
    activeKey = record.key;
    refreshState(record);
  }

  function compactInactive() {
    window.clearTimeout(compactTimer);
    compactTimer = window.setTimeout(() => {
      records.forEach(record => {
        if (record.key === activeKey) {
          mountAll(record);
          record.strip.style.removeProperty('display');
          record.strip.dataset.mobileV39Closed = '0';
          record.strip.removeAttribute('aria-hidden');
          refreshState(record);
        } else {
          compactRecord(record);
        }
      });
    }, 0);
  }

  function mountEverythingForNativeSync() {
    records.forEach(record => {
      mountAll(record);
      record.strip.style.removeProperty('display');
      record.strip.dataset.mobileV39Closed = '0';
      record.strip.removeAttribute('aria-hidden');
    });
  }

  function removeV36Controls() {
    host.querySelectorAll('.builder-mobile-group-toggle, .builder-mobile-group-state').forEach(node => node.remove());
  }

  function install() {
    if (installed || !isMobile()) return installed;
    const sections = [...host.querySelectorAll('[data-builder-group]')];
    if (!sections.length) return false;

    removeV36Controls();
    records = sections.map((section, index) => {
      const strip = section.querySelector('.choice-strip');
      const head = section.querySelector('.builder-group-head');
      if (!strip || !head) return null;

      const nodes = [...strip.children];
      const key = String(section.dataset.builderGroup || `group-${index}`);
      const state = document.createElement('small');
      state.className = 'builder-mobile-v39-state';
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'builder-mobile-v39-toggle';
      toggle.setAttribute('aria-expanded', 'false');
      toggle.textContent = 'Configurar';
      head.append(toggle, state);

      const record = {section, strip, head, nodes, key, state, toggle, cache:null};
      toggle.addEventListener('click', () => {
        if (activeKey === key && toggle.getAttribute('aria-expanded') === 'true') {
          activeKey = '';
          compactRecord(record);
          return;
        }
        expandRecord(record);
      });
      return record;
    }).filter(Boolean);

    if (!records.length) return false;
    installed = true;
    form.dataset.mobileVirtualized = '1';
    host.dataset.mobileVirtualized = '1';

    const count = document.querySelector('#project-builder-selection-count');
    if (count) {
      count.removeAttribute('id');
      count.textContent = 'Seleções preservadas';
    }

    activeKey = records[0].key;
    records.forEach(record => {
      if (record.key === activeKey) expandRecord(record);
      else compactRecord(record);
    });

    form.addEventListener('click', event => {
      if (!event.target.closest?.('[data-builder-preset]')) return;
      mountEverythingForNativeSync();
      compactInactive();
    }, true);
    form.addEventListener('reset', () => {
      mountEverythingForNativeSync();
      compactInactive();
    }, true);

    host.addEventListener('click', event => {
      const card = event.target.closest?.('.choice-card');
      if (!card) return;
      window.setTimeout(() => {
        const section = card.closest('[data-builder-group]');
        const record = records.find(item => item.section === section);
        if (record) refreshState(record);
      }, 0);
    });

    const hero = form.querySelector('.project-builder-hero p');
    if (hero) hero.textContent = 'No celular, abra somente a categoria que deseja configurar. As demais opções ficam fora do DOM visual para manter a tela leve.';

    document.dispatchEvent(new CustomEvent('devpilot:project-builder-mobile-virtualized', {
      detail:{groups:records.length},
    }));
    console.info(`[DevPilot] Project Builder Mobile V39 virtualizado · ${records.length} grupos`);
    return true;
  }

  installStyle();
  observer = new MutationObserver(() => {
    if (install()) observer?.disconnect();
  });
  observer.observe(host, {childList:true, subtree:false});
  if (install()) observer.disconnect();

  document.addEventListener('devpilot:view-changed', event => {
    if (event.detail?.view === 'new-project') installStyle();
  });
})();
