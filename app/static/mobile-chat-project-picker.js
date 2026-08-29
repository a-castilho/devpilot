(() => {
  'use strict';

  if (window.__devpilotMobileChatProjectPickerReady) return;
  window.__devpilotMobileChatProjectPickerReady = true;
  if (!window.matchMedia('(max-width: 900px)').matches) return;

  const select = document.querySelector('#voice-modal #voice-project');
  const control = select?.closest('.voice-project-control');
  if (!select || !control || control.querySelector('.mobile-chat-project-picker')) return;

  const style = document.createElement('style');
  style.textContent = `
    @media (max-width: 900px) {
      #voice-modal .voice-project-control > #voice-project {
        position: absolute !important; width: 1px !important; height: 1px !important;
        opacity: 0 !important; pointer-events: none !important; overflow: hidden !important;
      }
      #voice-modal .mobile-chat-project-picker { position: relative; width: 100%; }
      #voice-modal .mobile-chat-project-trigger {
        width: 100%; min-height: 48px; display: flex; align-items: center; justify-content: space-between;
        gap: 12px; padding: 11px 14px; border: 1px solid rgba(148,163,184,.22); border-radius: 13px;
        background: rgba(15,23,42,.72); color: #e6eef2; text-align: left; font: inherit; touch-action: manipulation;
      }
      #voice-modal .mobile-chat-project-trigger::after { content: '⌄'; color: #91a0aa; }
      #voice-modal .mobile-chat-project-list {
        position: absolute; z-index: 40; top: calc(100% + 6px); left: 0; right: 0;
        max-height: min(42vh, 320px); overflow: auto; overscroll-behavior: contain;
        padding: 6px; border: 1px solid rgba(148,163,184,.24); border-radius: 14px;
        background: #0b141c; box-shadow: 0 18px 42px rgba(0,0,0,.46);
      }
      #voice-modal .mobile-chat-project-list[hidden] { display: none !important; }
      #voice-modal .mobile-chat-project-option {
        width: 100%; min-height: 46px; display: flex; align-items: center; padding: 10px 12px;
        border: 0; border-radius: 10px; background: transparent; color: #dce8ed; text-align: left; font: inherit;
      }
      #voice-modal .mobile-chat-project-option[aria-selected="true"] { background: rgba(45,212,191,.13); color: #effffd; }
      #voice-modal .mobile-chat-project-empty { padding: 12px; color: #91a0aa; font-size: .86rem; }
    }
  `;
  document.head.appendChild(style);

  select.setAttribute('aria-hidden', 'true');
  select.tabIndex = -1;

  const picker = document.createElement('div');
  picker.className = 'mobile-chat-project-picker';
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'mobile-chat-project-trigger';
  trigger.setAttribute('aria-haspopup', 'listbox');
  trigger.setAttribute('aria-expanded', 'false');
  trigger.setAttribute('aria-label', 'Selecionar projeto do Chat DevPilot');
  trigger.textContent = 'Selecionar projeto';

  const list = document.createElement('div');
  list.className = 'mobile-chat-project-list';
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-label', 'Projetos disponíveis');
  list.hidden = true;
  picker.append(trigger, list);
  control.appendChild(picker);

  const selectedOption = () => [...select.options].find(option => option.selected) || select.options[0] || null;
  const optionText = option => String(option?.textContent || '').trim() || 'Geral — sem projeto';
  const syncTrigger = () => { const selected = selectedOption(); trigger.textContent = selected ? optionText(selected) : 'Selecionar projeto'; };
  const close = () => { list.hidden = true; trigger.setAttribute('aria-expanded', 'false'); };

  function renderList() {
    const options = [...select.options];
    list.replaceChildren();
    if (!options.length) {
      const empty = document.createElement('div');
      empty.className = 'mobile-chat-project-empty';
      empty.textContent = 'Nenhum projeto disponível.';
      list.appendChild(empty);
      return;
    }
    options.forEach(option => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'mobile-chat-project-option';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', String(option.selected));
      button.dataset.value = option.value;
      button.textContent = optionText(option);
      button.addEventListener('click', () => {
        select.value = option.value;
        select.dispatchEvent(new Event('change', {bubbles: true}));
        syncTrigger();
        close();
        trigger.focus({preventScroll: true});
      });
      list.appendChild(button);
    });
  }

  trigger.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    if (!list.hidden) return close();
    syncTrigger();
    renderList();
    list.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
  });
  picker.addEventListener('click', event => event.stopPropagation());
  select.addEventListener('change', syncTrigger);
  document.addEventListener('click', close);
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || list.hidden) return;
    close();
    trigger.focus({preventScroll: true});
  });
})();