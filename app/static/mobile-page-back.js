(() => {
  'use strict';

  if (window.__devpilotMobilePageBackReady) return;
  window.__devpilotMobilePageBackReady = true;

  const MOBILE_MAX = 900;
  const CONTROL_CLASS = 'mobile-page-back';
  const STYLE_ID = 'devpilot-mobile-page-back-style';

  const activeView = () => document.querySelector('main > .view.active');
  const sourceNav = () => document.querySelector('.sidebar > nav');

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      @media (max-width: ${MOBILE_MAX}px) {
        main > .view.active > .${CONTROL_CLASS} {
          position: sticky;
          top: 8px;
          z-index: 34;
          display: inline-flex;
          align-items: center;
          gap: 9px;
          min-height: 44px;
          margin: 0 0 14px;
          padding: 0 16px;
          border: 1px solid rgba(80, 219, 222, .34);
          border-radius: 14px;
          background: linear-gradient(180deg, rgba(17, 45, 66, .96), rgba(8, 26, 42, .96));
          box-shadow: 0 10px 28px rgba(0, 0, 0, .28), inset 0 1px 0 rgba(255,255,255,.04);
          color: #eefaff;
          font: inherit;
          font-weight: 800;
          letter-spacing: .01em;
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          cursor: pointer;
          touch-action: manipulation;
        }
        main > .view.active > .${CONTROL_CLASS}::before {
          content: '‹';
          display: grid;
          place-items: center;
          width: 24px;
          height: 24px;
          border-radius: 8px;
          background: rgba(77, 208, 225, .10);
          color: #6ff3e7;
          font-size: 28px;
          font-weight: 400;
          line-height: 1;
        }
        main > .view.active > .${CONTROL_CLASS}:active {
          transform: translateY(1px);
        }
        body.mobile-route #tasks-v9-back,
        body.mobile-route .project-builder-back {
          display: none !important;
        }
      }
      @media (min-width: ${MOBILE_MAX + 1}px) {
        .${CONTROL_CLASS} { display: none !important; }
      }
    `;
    document.head.appendChild(style);
  }

  function destinationFor(view) {
    if (!view) return 'overview';
    if (view.id === 'new-project-view') return 'projects';
    return 'overview';
  }

  function labelFor(view) {
    if (!view) return 'Voltar';
    if (view.id === 'new-project-view') return 'Voltar para Projetos';
    return 'Voltar ao Início';
  }

  function navigate(target) {
    const button = sourceNav()?.querySelector(`.nav[data-view="${CSS.escape(target)}"]`);
    if (button) {
      button.click();
      return;
    }
    window.location.hash = target === 'overview' ? '#overview' : `#${target}`;
  }

  function mount() {
    ensureStyle();
    if (window.innerWidth > MOBILE_MAX) return;

    document.querySelectorAll(`.${CONTROL_CLASS}`).forEach(button => {
      if (!button.closest('main > .view.active')) button.remove();
    });

    const view = activeView();
    if (!view || view.id === 'overview-view') return;
    if (view.querySelector(`:scope > .${CONTROL_CLASS}`)) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = CONTROL_CLASS;
    button.setAttribute('aria-label', labelFor(view));
    button.textContent = labelFor(view);
    button.addEventListener('click', () => navigate(destinationFor(view)));
    view.prepend(button);
  }

  let frame = 0;
  function schedule() {
    if (frame) return;
    frame = window.requestAnimationFrame(() => {
      frame = 0;
      mount();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedule, {once: true});
  } else {
    schedule();
  }

  document.addEventListener('devpilot:view-changed', schedule);
  document.addEventListener('devpilot:page-ready', schedule);
  document.addEventListener('devpilot:feature-ready', schedule);
  window.addEventListener('resize', schedule, {passive: true});
})();
