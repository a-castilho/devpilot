(() => {
  'use strict';

  const host = window.location.hostname.toLowerCase();
  const homologHost =
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host.endsWith('.vercel.app') ||
    host.endsWith('.onrender.com') ||
    host.includes('homolog');

  if (!homologHost) return;

  const PICKER_ID = 'acs-homolog-theme-picker';
  const STYLE_ID = 'acs-homolog-theme-picker-style';
  const STORAGE_KEY = 'acs.homolog.workspace-tone';
  const tones = [
    { id: 'black', label: 'Preto', swatch: '#050505' },
    { id: 'graphite', label: 'Grafite', swatch: '#363a40' },
    { id: 'rose', label: 'Rosa', swatch: '#ff4775' },
    { id: 'blue', label: 'Azul', swatch: '#6284f5' },
    { id: 'mint', label: 'Verde', swatch: '#46d5a5' },
    { id: 'white', label: 'Branco', swatch: '#f8fafc' },
  ];

  function install() {
    if (document.getElementById(PICKER_ID)) return;

    document.querySelectorAll('.workspace-tone-picker').forEach((element) => element.remove());

    if (!document.getElementById(STYLE_ID)) {
      const style = document.createElement('style');
      style.id = STYLE_ID;
      style.textContent = `
        html[data-workspace-tone="rose"]{--bg:#1a0b12;--panel:#231018;--panel2:#311522;--surface:#231018;--surface2:#311522;--line:#5a2338;--text:#fff3f7;--muted:#d4a9b7;--green:#ff4775;--green2:#ff6b91;--cyan:#ff4775;--workspace-glow:#ff477533;--workspace-sidebar:#16090ff2}
        html[data-workspace-tone="blue"]{--bg:#081225;--panel:#0d1a33;--panel2:#122545;--surface:#0d1a33;--surface2:#122545;--line:#294b7d;--text:#eef4ff;--muted:#9eb2d3;--green:#6284f5;--green2:#7a99ff;--cyan:#77a3ff;--workspace-glow:#6284f538;--workspace-sidebar:#07101ff2}
        html[data-workspace-tone="mint"]{--bg:#071510;--panel:#0b2018;--panel2:#103126;--surface:#0b2018;--surface2:#103126;--line:#245941;--text:#effff8;--muted:#9fc7b5;--green:#46d5a5;--green2:#69e4bc;--cyan:#5ce0b5;--workspace-glow:#46d5a538;--workspace-sidebar:#07140ff2}
        html[data-workspace-tone="white"]{--bg:#f4f6f8;--panel:#ffffff;--panel2:#eef2f6;--surface:#ffffff;--surface2:#eef2f6;--line:#d7dde5;--text:#18212f;--muted:#667085;--green:#0d9f63;--green2:#078450;--cyan:#0f766e;--workspace-glow:#dbeafe;--workspace-sidebar:#f8fafcee}
        html[data-workspace-tone]{background:var(--bg,inherit)}
        html[data-workspace-tone] body{background-color:var(--bg,inherit);transition:background-color .2s ease}
        #${PICKER_ID}{position:fixed;top:10px;right:10px;z-index:2147483000;display:flex;align-items:center;gap:5px;font:600 12px/1 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
        #${PICKER_ID} .acs-homolog-tone-menu{display:flex;align-items:center;gap:6px;max-width:0;opacity:0;overflow:hidden;padding:0;border:1px solid transparent;border-radius:12px;background:rgba(12,15,20,.9);box-shadow:0 12px 32px rgba(0,0,0,.34);backdrop-filter:blur(14px);transform:translateX(7px);pointer-events:none;transition:max-width .24s ease,opacity .16s ease,transform .2s ease,padding .2s ease,border-color .2s ease}
        #${PICKER_ID}.open .acs-homolog-tone-menu{max-width:260px;opacity:1;padding:6px 7px;border-color:rgba(255,255,255,.16);transform:translateX(0);pointer-events:auto}
        #${PICKER_ID} .acs-homolog-tone-option{width:21px;height:21px;flex:0 0 21px;padding:0;border:1px solid rgba(255,255,255,.35);border-radius:50%;background:var(--tone);cursor:pointer;box-shadow:inset 0 0 0 1px rgba(0,0,0,.12);transition:transform .14s ease,box-shadow .14s ease,border-color .14s ease}
        #${PICKER_ID} .acs-homolog-tone-option:hover{transform:scale(1.1)}
        #${PICKER_ID} .acs-homolog-tone-option[aria-pressed="true"]{border-color:#fff;box-shadow:0 0 0 2px rgba(255,255,255,.28),inset 0 0 0 1px rgba(0,0,0,.18)}
        #${PICKER_ID} .acs-homolog-tone-toggle{width:29px;height:29px;display:grid;place-items:center;padding:0;border:1px solid rgba(255,255,255,.16);border-radius:10px;background:rgba(12,15,20,.92);color:#f8fafc;cursor:pointer;box-shadow:0 10px 28px rgba(0,0,0,.3);font-size:16px;font-weight:800;line-height:1;transition:border-color .16s ease,background .16s ease,transform .16s ease}
        #${PICKER_ID} .acs-homolog-tone-toggle:hover,#${PICKER_ID} .acs-homolog-tone-toggle[aria-expanded="true"]{border-color:var(--acs-homolog-accent,#6284f5);background:rgba(20,25,32,.98)}
        #${PICKER_ID}.open .acs-homolog-tone-toggle{transform:rotate(180deg)}
        @media(max-width:640px){#${PICKER_ID}{top:8px;right:8px}#${PICKER_ID}.open .acs-homolog-tone-menu{max-width:220px;gap:5px;padding:5px 6px}#${PICKER_ID} .acs-homolog-tone-option{width:20px;height:20px;flex-basis:20px}}
        @media(prefers-reduced-motion:reduce){#${PICKER_ID} *{transition:none!important}}
      `;
      document.head.appendChild(style);
    }

    const picker = document.createElement('div');
    picker.id = PICKER_ID;
    picker.setAttribute('aria-label', 'Cores do ambiente de homologação');
    picker.innerHTML = `
      <div class="acs-homolog-tone-menu" role="group" aria-label="Escolher cor do ambiente">
        ${tones.map((tone) => `<button type="button" class="acs-homolog-tone-option" data-tone="${tone.id}" aria-label="${tone.label}" title="${tone.label}" aria-pressed="false" style="--tone:${tone.swatch}"></button>`).join('')}
      </div>
      <button type="button" class="acs-homolog-tone-toggle" aria-label="Abrir seletor de cores" title="Cores" aria-expanded="false">›</button>
    `;
    document.body.appendChild(picker);

    const toggle = picker.querySelector('.acs-homolog-tone-toggle');
    const options = [...picker.querySelectorAll('.acs-homolog-tone-option')];

    const setOpen = (open) => {
      picker.classList.toggle('open', open);
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Recolher seletor de cores' : 'Abrir seletor de cores');
    };

    const applyTone = (toneId) => {
      const tone = tones.find((item) => item.id === toneId) || tones[0];
      document.documentElement.dataset.workspaceTone = tone.id;
      document.documentElement.style.setProperty('--acs-homolog-accent', tone.swatch);
      localStorage.setItem(STORAGE_KEY, tone.id);
      options.forEach((option) => option.setAttribute('aria-pressed', String(option.dataset.tone === tone.id)));
      const themeMeta = document.querySelector('meta[name="theme-color"]');
      if (themeMeta) themeMeta.setAttribute('content', tone.swatch);
    };

    const saved = localStorage.getItem(STORAGE_KEY);
    applyTone(tones.some((tone) => tone.id === saved) ? saved : 'black');
    setOpen(false);

    toggle.addEventListener('click', (event) => {
      event.stopPropagation();
      setOpen(!picker.classList.contains('open'));
    });

    options.forEach((option) => {
      option.addEventListener('click', (event) => {
        event.stopPropagation();
        applyTone(option.dataset.tone);
        setOpen(false);
      });
    });

    document.addEventListener('click', (event) => {
      if (!picker.contains(event.target)) setOpen(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') setOpen(false);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
})();
