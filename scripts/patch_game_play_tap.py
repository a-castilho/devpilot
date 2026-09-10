from pathlib import Path

path = Path('app/static/game/objective-controls.js')
text = path.read_text(encoding='utf-8')
old = """      button.onclick = async () => {
        const projectId = project?.value || '';
        const targetGoal = goal?.value || '';
        button.disabled = true;
        button.textContent = '🚀 Iniciando rodada…';
        status.classList.remove('game74-error');
        status.innerHTML = '<strong>Rodada iniciada.</strong> Criando Planejamento na esteira real…';
        try {
          await engine.startRound({projectId, goal: targetGoal});
          localStorage.removeItem(DRAFT_GOAL_KEY);
          localStorage.setItem(DRAFT_PROJECT_KEY, projectId);
        } catch (error) {
          button.disabled = false;
          button.textContent = '🚀 Jogar agora';
          status.classList.add('game74-error');
          status.textContent = error?.message || 'Falha ao iniciar a rodada';
        }
      };
"""
new = """      let startInFlight = false;
      let pointerStartedAt = 0;
      const startRoundFromUi = async event => {
        event?.preventDefault?.();
        if (startInFlight) return;
        const projectId = String(project?.value || '').trim();
        const targetGoal = String(goal?.value || '').trim();
        if (!projectId || targetGoal.length < 3) {
          syncStartState();
          goal?.focus();
          return;
        }
        startInFlight = true;
        button.disabled = true;
        button.textContent = '🚀 Iniciando rodada…';
        status.classList.remove('game74-error');
        status.innerHTML = '<strong>Rodada iniciada.</strong> Criando Planejamento na esteira real…';
        try {
          const liveEngine = controller();
          if (!liveEngine || typeof liveEngine.startRound !== 'function') throw new Error('Controlador do jogo ainda não está pronto');
          await liveEngine.startRound({projectId, goal: targetGoal});
          localStorage.removeItem(DRAFT_GOAL_KEY);
          localStorage.setItem(DRAFT_PROJECT_KEY, projectId);
          document.dispatchEvent(new CustomEvent('devpilot:game:rendered', {detail:{source:'game74-start'}}));
        } catch (error) {
          startInFlight = false;
          button.disabled = false;
          button.textContent = '🚀 Jogar agora';
          status.classList.add('game74-error');
          status.textContent = error?.message || 'Falha ao iniciar a rodada';
        }
      };
      button.addEventListener('pointerup', event => {
        if (event.pointerType && event.pointerType !== 'touch' && event.pointerType !== 'pen') return;
        pointerStartedAt = Date.now();
        void startRoundFromUi(event);
      });
      button.addEventListener('click', event => {
        if (Date.now() - pointerStartedAt < 900) {
          event.preventDefault();
          return;
        }
        void startRoundFromUi(event);
      });
"""
if old not in text:
    raise SystemExit('handler antigo não encontrado')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
