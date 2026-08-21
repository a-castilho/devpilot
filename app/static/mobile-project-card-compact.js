(() => {
  const STYLE_ID = 'devpilot-mobile-project-card-compact-style';

  if (document.getElementById(STYLE_ID)) return;

  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    @media (max-width: 900px) {
      #projects-view .project-card > p,
      #projects-view .project-card > code,
      #projects-view .project-card .list-row > small {
        display: none !important;
      }

      #projects-view .project-card {
        min-height: 0;
        padding: 18px;
      }

      #projects-view .project-card h3 {
        margin: 8px 0 14px;
      }

      #projects-view .project-card .list-row {
        display: flex;
        justify-content: flex-end;
        padding: 0;
        border-top: 0;
      }

      #projects-view .project-card .list-row > div:last-child {
        display: flex;
        width: 100%;
        justify-content: flex-end;
        gap: 8px;
        flex-wrap: wrap;
      }
    }
  `;
  document.head.appendChild(style);
})();
