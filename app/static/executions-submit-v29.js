(() => {
  'use strict';

  /*
   * RETIRADO — V29 não pode mais possuir o submit de #task-form.
   *
   * O fluxo canônico de cadastro vive em task-modal.js (V30+), carregado pelo
   * feature-loader quando o usuário abre Nova execução. Manter um interceptor
   * global aqui causava disputa de handlers e reintroduzia payloads antigos,
   * inclusive source=global/project, rejeitados pelo TaskCreate com HTTP 422.
   *
   * O arquivo permanece como stub temporário porque versões antigas de
   * viewport-adaptive-v15.js ainda podem solicitá-lo em cache. Carregá-lo é
   * intencionalmente inofensivo.
   */
  window.__devpilotExecutionsSubmitV29Retired = true;
  console.info('[DevPilot] Execução Submit V29 aposentado; V30+ é canônico');
})();
