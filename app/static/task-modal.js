(() => {
  const form = document.querySelector('#task-form');
  const mode = document.querySelector('#task-mode');
  const context = document.querySelector('#task-context');
  const hint = document.querySelector('#task-mode-hint');
  const assistTitle = document.querySelector('#task-assist-title');
  const assistText = document.querySelector('#task-assist-text');
  const submit = document.querySelector('#task-submit');

  if (!form || !mode || !context) return;

  const modes = {
    'analysis-read-only': {
      title: 'Análise assistida pelo AgentOS',
      text: 'O repositório será consultado em uma área isolada. Nenhuma alteração será persistida; a resposta destacará evidências, riscos, impacto e recomendações.',
      hint: 'A IA analisará este contexto junto com o repositório, sem persistir alterações.',
      submit: 'Registrar análise',
      instruction: 'Faça uma análise/diagnóstico do contexto informado. Investigue o repositório, cite evidências concretas e produza achados priorizados com risco, impacto, recomendação e esforço estimado. Não implemente mudanças e não persista alterações em arquivos.'
    },
    develop: {
      title: 'Desenvolvimento assistido pelo AgentOS',
      text: 'Antes de alterar código, o DevPilot verifica se a funcionalidade já existe para evitar telas, endpoints, serviços ou fluxos duplicados.',
      hint: 'A primeira etapa é uma verificação obrigatória de duplicidade. Só depois a IA implementa o que realmente estiver faltando.',
      submit: 'Registrar desenvolvimento',
      instruction: 'Comece obrigatoriamente verificando no repositório se o comportamento solicitado já existe, inclusive em telas, rotas, componentes, serviços, modelos, testes e documentação relacionados. Não crie uma segunda implementação do que já existe. Se estiver completo, apenas valide e apresente evidências sem alterar código. Se estiver parcial, reutilize a implementação existente e desenvolva somente as lacunas comprovadas. Depois execute as verificações relevantes e resuma o preflight, as alterações e os riscos remanescentes.'
    },
    fix: {
      title: 'Correção assistida pelo AgentOS',
      text: 'O DevPilot investiga a causa raiz, aplica uma correção mínima e valida a regressão antes de devolver o resultado para revisão.',
      hint: 'Descreva o erro observado, comportamento esperado e evidências disponíveis.',
      submit: 'Registrar correção',
      instruction: 'Diagnostique a causa raiz do problema descrito e implemente uma correção mínima e segura. Preserve compatibilidade, execute testes de regressão relevantes e resuma evidências e riscos.'
    },
    review: {
      title: 'Revisão assistida pelo AgentOS',
      text: 'O DevPilot revisa o contexto e o repositório para apontar regressões, inconsistências e oportunidades antes de qualquer alteração.',
      hint: 'A revisão não solicita implementação automática; qualquer mudança posterior deve ser criada como nova tarefa.',
      submit: 'Registrar revisão',
      instruction: 'Revise o contexto e o repositório. Identifique regressões, inconsistências, riscos de segurança, lacunas de testes e oportunidades. Não implemente mudanças nesta tarefa.'
    }
  };

  function refreshMode() {
    const config = modes[mode.value] || modes['analysis-read-only'];
    if (hint) hint.textContent = config.hint;
    if (assistTitle) assistTitle.textContent = config.title;
    if (assistText) assistText.textContent = config.text;
    if (submit) submit.textContent = config.submit;
  }

  mode.addEventListener('change', refreshMode);
  refreshMode();

  form.addEventListener('submit', () => {
    const raw = context.value.trim();
    const selectedMode = mode.value;
    const config = modes[selectedMode] || modes['analysis-read-only'];
    context.value = `[DEVPILOT_MODE=${selectedMode}]\n${config.instruction}\n\nContexto do usuário:\n${raw}`;
    window.setTimeout(() => {
      context.value = raw;
    }, 0);
  }, true);

  form.addEventListener('reset', () => {
    window.setTimeout(refreshMode, 0);
  });
})();
