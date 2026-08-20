(() => {
  const MOBILE = matchMedia('(max-width:760px)').matches || matchMedia('(pointer:coarse)').matches;
  if (!MOBILE || document.getElementById('repeatai-mobile-viewport-fix')) return;

  const style = document.createElement('style');
  style.id = 'repeatai-mobile-viewport-fix';
  style.textContent = `
    @media(max-width:760px){
      #project-example-view .example-project-stage{
        height:620px!important;
        min-height:620px!important;
        max-height:620px!important;
        overflow:hidden!important;
        contain:layout paint style!important;
        box-shadow:none!important
      }
      #project-example-view .example-project-frame{
        display:block!important;
        width:100%!important;
        height:620px!important;
        min-height:620px!important;
        max-height:620px!important
      }
    }
  `;
  document.head.appendChild(style);
})();