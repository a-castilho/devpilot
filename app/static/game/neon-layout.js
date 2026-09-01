(() => {
  'use strict';

  if (window.__devpilotGameNeonV48) return;
  window.__devpilotGameNeonV48 = true;

  const VIEW_ID = 'build-game-view';
  const LAYOUT_CLASS = 'game-neon-v48';
  const NAV_ID = 'game-neon-bottom-nav';
  const BRAND_ID = 'game-neon-brand';
  const XP_ID = 'game-neon-xp';

  const phaseBullets = Object.freeze({
    1: [
      'Objetivo e critérios de vitória definidos.',
      'Stack e comandos reais identificados.',
      'Baseline verificável antes da implementação.',
      'Próximo incremento registrado no projeto.',
    ],
    2: [
      'Fatia funcional de ponta a ponta.',
      'Mudança material e observável no repositório.',
      'Teste automático cobrindo o comportamento criado.',
      'Evidência do delta antes e depois.',
    ],
    3: [
      'Regras de negócio e limites de acesso.',
      'Cenários positivos e negativos cobertos.',
      'Autorização, validação e isolamento revisados.',
      'Falhas reais corrigidas sem bypass.',
    ],
    4: [
      'Fluxo principal claro e utilizável.',
      'Estados de carregamento, vazio, sucesso e erro.',
      'Responsividade e acessibilidade preservadas.',
      'Comportamento final validado no código.',
    ],
    5: [
      'Suíte aplicável executada de verdade.',
      'Lint, build e testes relevantes validados.',
      'Falhas corrigidas sem silenciar verificações.',
      'Cobertura reforçada para o objetivo da missão.',
    ],
    6: [
      'Critérios de aceite revisados contra a entrega.',
      'Build e smoke final executados.',
      'Configuração, segurança e documentação revisadas.',
      'Entrega encerrada somente com evidência real.',
    ],
  });

  const normalize = value => String(value || '')
    .trim()
    .toLowerCase()
    .replaceAll(' ', '_');

  const phaseNumber = card => {
    const label = String(card?.querySelector('.build-game-phase-copy small')?.textContent || '');
    return Number(label.match(/FASE\s+(\d+)\s*\//i)?.[1] || 0);
  };

  const phaseTotal = view => view?.querySelectorAll('.build-game-phase')?.length || 6;

  function earnedXp(view) {
    const raw = String(view?.querySelector('.build-game-score > div:nth-child(2) strong')?.textContent || '0 XP');
    const value = raw.split('/')[0].trim();
    return /xp/i.test(value) ? value : `${value || '0'} XP`;
  }

  function projectName(view) {
    return String(
      view?.querySelector('.build-game-score > div:nth-child(3) strong')?.textContent ||
      document.querySelector('#build-game-project option:checked')?.textContent ||
      'Projeto ativo'
    ).trim();
  }

  function progressState(view) {
    const cards = [...(view?.querySelectorAll('.build-game-phase') || [])];
    const total = Math.max(1, cards.length || 6);
    const passed = cards.filter(card => card.classList.contains('passed')).length;
    return {passed, total, percent:Math.round(passed / total * 100)};
  }

  function installHeader(view) {
    const hud = document.querySelector('.devpilot-game-hud');
    if (!hud) return;

    let brand = document.getElementById(BRAND_ID);
    if (!brand) {
      brand = document.createElement('div');
      brand.id = BRAND_ID;
      brand.className = 'devpilot-game-brand';
      brand.innerHTML = `
        <span class="devpilot-game-brand-mark" aria-hidden="true">DP</span>
        <span class="devpilot-game-brand-copy"><strong>DevPilot</strong><span>MODO JOGO</span></span>
      `;
      const copy = hud.querySelector('.devpilot-game-hud-copy');
      hud.insertBefore(brand, copy || hud.children[1] || null);
    }

    let xp = document.getElementById(XP_ID);
    if (!xp) {
      xp = document.createElement('span');
      xp.id = XP_ID;
      xp.className = 'devpilot-game-xp-badge';
      hud.appendChild(xp);
    }
    xp.textContent = earnedXp(view);
  }

  function installMissionCard(view) {
    const shell = view.querySelector('.build-game-shell');
    if (!shell) return;

    const state = progressState(view);
    let card = shell.querySelector('.game-neon-mission');
    if (!card) {
      card = document.createElement('section');
      card.className = 'game-neon-mission';
      shell.insertBefore(card, shell.firstElementChild);
    }

    card.innerHTML = `
      <div class="game-neon-mission-copy">
        <small>MISSÃO ATIVA</small>
        <strong></strong>
      </div>
      <div class="game-neon-mission-count">
        <b>${state.passed}/${state.total}</b>
        <span>FASES</span>
      </div>
      <i class="game-neon-mission-progress" style="width:calc((100% - 40px) * ${state.percent / 100})"></i>
    `;
    card.querySelector('.game-neon-mission-copy strong').textContent = projectName(view);
  }

  function statusLabel(card) {
    const status = card.querySelector('.status');
    if (!status) return '';
    return normalize(status.textContent).toUpperCase().replaceAll('_', ' ');
  }

  function installCurrentPhase(view) {
    const cards = [...view.querySelectorAll('.build-game-phase')];
    cards.forEach(card => card.classList.remove('game-neon-current'));

    const current = view.querySelector('.build-game-phase.current') ||
      cards.find(card => !card.classList.contains('passed') && !card.classList.contains('locked')) ||
      cards[cards.length - 1];
    if (!current) return;

    current.classList.add('game-neon-current');
    const number = phaseNumber(current) || 1;
    const total = phaseTotal(view);
    const copy = current.querySelector('.build-game-phase-copy');
    const actions = current.querySelector('.build-game-phase-actions');
    if (!copy || !actions) return;

    let numberBlock = current.querySelector('.game-neon-phase-number');
    if (!numberBlock) {
      numberBlock = document.createElement('div');
      numberBlock.className = 'game-neon-phase-number';
      current.insertBefore(numberBlock, current.firstElementChild);
    }
    numberBlock.innerHTML = `<small>FASE</small><strong>${String(number).padStart(2, '0')}</strong><i></i>`;

    let top = copy.querySelector('.game-neon-current-top');
    if (!top) {
      top = document.createElement('div');
      top.className = 'game-neon-current-top';
      copy.insertBefore(top, copy.firstChild);
    }
    const currentStatus = statusLabel(current);
    const approvalChip = currentStatus === 'AWAITING APPROVAL'
      ? '<span class="game-neon-chip approval">AWAITING APPROVAL</span>'
      : (currentStatus ? `<span class="game-neon-chip">${currentStatus}</span>` : '');
    top.innerHTML = `<span class="game-neon-chip">SKILLS</span>${approvalChip}`;

    let bullets = copy.querySelector('.game-neon-bullets');
    if (!bullets) {
      bullets = document.createElement('ul');
      bullets.className = 'game-neon-bullets';
      copy.appendChild(bullets);
    }
    bullets.innerHTML = (phaseBullets[number] || phaseBullets[1])
      .map(item => `<li>${item}</li>`)
      .join('');

    const existingContinue = actions.querySelector('.game-neon-continue');
    if (!existingContinue && !current.classList.contains('passed')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'ghost game-neon-continue';
      button.textContent = number >= total ? 'Revisar' : 'Continuar';
      button.addEventListener('click', async () => {
        button.disabled = true;
        const original = button.textContent;
        button.textContent = 'Atualizando…';
        try {
          await window.loadBuildGame?.();
          document.querySelector('.game-neon-current')?.scrollIntoView?.({block:'center'});
        } finally {
          button.disabled = false;
          button.textContent = original;
        }
      });
      actions.appendChild(button);
    }
  }

  function installBottomNav() {
    if (document.getElementById(NAV_ID)) return;
    const nav = document.createElement('nav');
    nav.id = NAV_ID;
    nav.className = 'game-neon-bottom-nav';
    nav.setAttribute('aria-label', 'Navegação do DevPilot');
    nav.innerHTML = `
      <button type="button" data-game-nav="home"><b>⌂</b><span>Início</span></button>
      <button type="button" class="active" data-game-nav="projects"><b>▣</b><span>Projetos</span></button>
      <button type="button" data-game-nav="tasks"><b>▷</b><span>Execuções</span></button>
      <button type="button" data-game-nav="menu"><b>☰</b><span>Menu</span></button>
    `;
    document.body.appendChild(nav);

    nav.querySelector('[data-game-nav="home"]')?.addEventListener('click', () => window.location.assign('/'));
    nav.querySelector('[data-game-nav="projects"]')?.addEventListener('click', () => window.location.assign('/#/projects'));
    nav.querySelector('[data-game-nav="tasks"]')?.addEventListener('click', () => window.location.assign('/#/tasks'));
    nav.querySelector('[data-game-nav="menu"]')?.addEventListener('click', () => window.location.assign('/#menu'));
  }

  function applyLayout() {
    const view = document.getElementById(VIEW_ID);
    if (!view?.querySelector('.build-game-shell')) return false;
    view.classList.add(LAYOUT_CLASS);
    installHeader(view);
    installMissionCard(view);
    installCurrentPhase(view);
    installBottomNav();
    document.documentElement.dataset.devpilotGameVisual = 'neon-v48';
    return true;
  }

  function wrapGameLoader() {
    const upstream = window.loadBuildGame;
    if (typeof upstream !== 'function' || upstream.__devpilotGameNeonV48) return;

    const wrapped = async function loadBuildGameNeon(...args) {
      const result = await upstream.apply(this, args);
      applyLayout();
      return result;
    };
    wrapped.__devpilotGameNeonV48 = true;
    wrapped.__devpilotUpstream = upstream;
    window.loadBuildGame = wrapped;
  }

  wrapGameLoader();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => void applyLayout(), {once:true});
  } else {
    void applyLayout();
  }
  document.addEventListener('devpilot:game:standalone-ready', () => void applyLayout());
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void applyLayout();
  });
})();
