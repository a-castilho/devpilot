(() => {
  const TABLE_ID = 'tasks-table';
  const COMPLETE_AT = 0.88;

  function injectStyles() {
    if (document.getElementById('approval-slider-styles')) return;
    const style = document.createElement('style');
    style.id = 'approval-slider-styles';
    style.textContent = `
      .approval-slider{
        --slide:0px;
        --slide-pct:0%;
        position:relative;
        width:min(320px,100%);
        min-width:210px;
        height:58px;
        border:1px solid #29445f;
        border-radius:999px;
        overflow:hidden;
        background:#081522;
        box-shadow:inset 0 0 0 1px rgba(255,255,255,.02);
        touch-action:pan-y;
        user-select:none;
        -webkit-user-select:none;
        transition:border-color .2s ease,background .2s ease,box-shadow .2s ease
      }
      .approval-slider-fill{
        position:absolute;
        inset:0 auto 0 0;
        width:var(--slide-pct);
        pointer-events:none;
        background:linear-gradient(90deg,#18b89c,#35df94);
        opacity:.35;
        transition:width .08s linear,opacity .2s ease
      }
      .approval-slider-label{
        position:absolute;
        inset:0 16px 0 72px;
        display:flex;
        align-items:center;
        justify-content:center;
        color:#a8bbcf;
        font-size:12px;
        font-weight:850;
        letter-spacing:.04em;
        text-transform:uppercase;
        pointer-events:none;
        white-space:nowrap;
        transition:color .2s ease
      }
      .approval-slider .approve{
        position:absolute!important;
        z-index:2;
        left:5px!important;
        top:5px!important;
        width:48px!important;
        min-width:48px!important;
        max-width:48px!important;
        height:48px!important;
        min-height:48px!important;
        padding:0!important;
        margin:0!important;
        border:0!important;
        border-radius:50%!important;
        display:grid!important;
        place-items:center!important;
        transform:translateX(var(--slide));
        background:linear-gradient(135deg,#38e0d2,#45aef8)!important;
        color:#06111b!important;
        box-shadow:0 7px 18px rgba(40,187,223,.28)!important;
        font-size:0!important;
        cursor:grab!important;
        touch-action:none!important;
        transition:transform .18s ease,background .2s ease,box-shadow .2s ease
      }
      .approval-slider .approve::before{
        content:'›';
        font-size:34px;
        font-weight:900;
        line-height:1;
        transform:translateY(-1px)
      }
      .approval-slider.dragging .approve{
        cursor:grabbing!important;
        transition:none
      }
      .approval-slider.dragging .approval-slider-fill{transition:none}
      .approval-slider.approved{
        border-color:#38dd8a;
        background:#09251c;
        box-shadow:0 0 0 3px rgba(56,221,138,.09),0 0 24px rgba(56,221,138,.12)
      }
      .approval-slider.approved .approval-slider-fill{
        width:100%!important;
        opacity:.6
      }
      .approval-slider.approved .approval-slider-label{
        inset:0 64px 0 16px;
        color:#d9ffea
      }
      .approval-slider.approved .approve{
        background:linear-gradient(135deg,#39e391,#20b86e)!important;
        color:#052014!important;
        box-shadow:0 7px 18px rgba(32,184,110,.28)!important
      }
      .approval-slider.approved .approve::before{
        content:'✓';
        font-size:23px
      }
      .approval-slider.error{
        border-color:#ff6577;
        box-shadow:0 0 0 3px rgba(255,101,119,.08)
      }
      @media(max-width:900px){
        .approval-slider{width:100%;max-width:100%;height:62px}
        .approval-slider .approve{width:52px!important;min-width:52px!important;max-width:52px!important;height:52px!important;min-height:52px!important}
        .approval-slider-label{inset:0 14px 0 76px;font-size:12px}
      }
    `;
    document.head.appendChild(style);
  }

  function setProgress(slider, px) {
    const thumb = slider.querySelector('.approve');
    if (!thumb) return 0;
    const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
    const value = Math.max(0, Math.min(max, px));
    const pct = max ? (value / max) * 100 : 0;
    slider.style.setProperty('--slide', `${value}px`);
    slider.style.setProperty('--slide-pct', `${pct}%`);
    slider.setAttribute('aria-valuenow', String(Math.round(pct)));
    return max ? value / max : 0;
  }

  function reset(slider) {
    slider.classList.remove('dragging', 'approved', 'error');
    slider.dataset.approving = '0';
    const label = slider.querySelector('.approval-slider-label');
    if (label) label.textContent = 'Deslize para aprovar';
    setProgress(slider, 0);
  }

  async function approve(slider) {
    if (slider.dataset.approving === '1') return;
    const button = slider.querySelector('.approve');
    const id = button?.dataset.id;
    if (!button || !id) return reset(slider);

    slider.dataset.approving = '1';
    slider.classList.remove('dragging', 'error');
    slider.classList.add('approved');
    const max = Math.max(0, slider.clientWidth - button.offsetWidth - 10);
    setProgress(slider, max);
    const label = slider.querySelector('.approval-slider-label');
    if (label) label.textContent = 'Aprovando…';
    button.disabled = true;

    try {
      if (typeof window.api !== 'function') throw new Error('API de aprovação indisponível');
      await window.api(`/tasks/${id}/approve`, {method:'POST'});
      if (label) label.textContent = 'Aprovado';
      if (typeof window.toast === 'function') window.toast('Tarefa aprovada e enfileirada');
      await new Promise(resolve => setTimeout(resolve, 350));
      if (typeof window.load === 'function') await window.load();
    } catch (error) {
      slider.classList.remove('approved');
      slider.classList.add('error');
      if (label) label.textContent = 'Falhou · tente novamente';
      button.disabled = false;
      if (typeof window.toast === 'function') window.toast(error?.message || 'Falha ao aprovar tarefa');
      setTimeout(() => reset(slider), 1300);
    }
  }

  function bind(slider) {
    if (slider.dataset.bound === '1') return;
    slider.dataset.bound = '1';
    const button = slider.querySelector('.approve');
    if (!button) return;

    let pointerId = null;
    let startX = 0;
    let startSlide = 0;

    button.setAttribute('aria-label', 'Arraste para a direita para aprovar a tarefa');
    button.title = 'Arraste para aprovar';

    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);

    button.addEventListener('pointerdown', event => {
      if (slider.dataset.approving === '1') return;
      pointerId = event.pointerId;
      startX = event.clientX;
      const current = parseFloat(getComputedStyle(slider).getPropertyValue('--slide')) || 0;
      startSlide = current;
      slider.classList.add('dragging');
      button.setPointerCapture?.(pointerId);
      event.preventDefault();
    });

    button.addEventListener('pointermove', event => {
      if (pointerId !== event.pointerId || !slider.classList.contains('dragging')) return;
      setProgress(slider, startSlide + event.clientX - startX);
      event.preventDefault();
    });

    const finish = event => {
      if (pointerId === null || (event.pointerId != null && event.pointerId !== pointerId)) return;
      const ratio = setProgress(slider, parseFloat(getComputedStyle(slider).getPropertyValue('--slide')) || 0);
      slider.classList.remove('dragging');
      pointerId = null;
      if (ratio >= COMPLETE_AT) approve(slider);
      else reset(slider);
    };

    button.addEventListener('pointerup', finish);
    button.addEventListener('pointercancel', finish);

    button.addEventListener('keydown', event => {
      if (event.key === 'End' || event.key === 'ArrowRight') {
        event.preventDefault();
        const max = Math.max(0, slider.clientWidth - button.offsetWidth - 10);
        setProgress(slider, max);
        approve(slider);
      }
    });
  }

  function enhance() {
    const table = document.getElementById(TABLE_ID);
    if (!table) return;

    table.querySelectorAll('button.approve').forEach(button => {
      if (button.closest('.approval-slider')) return;

      const slider = document.createElement('div');
      slider.className = 'approval-slider';
      slider.setAttribute('role', 'slider');
      slider.setAttribute('aria-label', 'Confirmação de aprovação');
      slider.setAttribute('aria-valuemin', '0');
      slider.setAttribute('aria-valuemax', '100');
      slider.setAttribute('aria-valuenow', '0');

      const fill = document.createElement('span');
      fill.className = 'approval-slider-fill';
      const label = document.createElement('span');
      label.className = 'approval-slider-label';
      label.textContent = 'Deslize para aprovar';

      button.parentNode.insertBefore(slider, button);
      slider.append(fill, label, button);
      bind(slider);
    });
  }

  injectStyles();
  enhance();

  const table = document.getElementById(TABLE_ID);
  if (table) {
    new MutationObserver(enhance).observe(table, {childList:true, subtree:true});
  }

  document.addEventListener('click', event => {
    if (event.target.closest?.('[data-view="tasks"]')) setTimeout(enhance, 0);
  }, {passive:true});
})();
