(() => {
  'use strict';

  if (window.__devpilotRuntimeManifest) return;

  const bundles = Object.freeze({
    shell: ['simplified-nav.js'],
    mobileShell: ['mobile-accordion-menu.js'],
    profile: ['profile.js'],
    users: ['users.js'],
    providers: ['provider-models.js', 'provider-ollama.js'],
    projectBuilder: [
      'project-provisioning.js',
      'project-builder.js',
      'project-description-profile.js',
      'mobile-project-card-compact.js',
    ],
    projects: [
      'project-delete-ui.js',
      'project-ships.js',
      'product-delivery-ui.js',
    ],
    taskModal: ['task-modal.js'],
    tasks: [
      'consolidated-ui.js',
      'task-modal.js',
      'task-analytics.js',
      'project-delete-ui.js',
      'task-completion-documentation.js',
      'system-tests.js',
      'task-workflow-observability.js',
      'task-failures.js',
      'task-image-upload.js',
      'analysis-commercial-proposal.js',
      'analysis-failure-actions.js',
      'analysis-incomplete-commercial.js',
      'approval-slider.js',
      'ui-literal-newline-cleanup.js',
    ],
    reports: [
      'reports.js',
      'repeatai-analysis-scroll.js',
      'repeatai-live-graphs.js',
      'repeatai-dashboard-graphs.js',
      'repeatai-pattern-graphs.js',
    ],
    organizations: ['organization-normalization-ui.js'],
    example: [
      'example-project.js',
      'example-project-mobile-training.js',
      'example-project-graphs-fix.js',
      'tws-example.js',
    ],
    voice: [
      'super-admin-voice.js',
      'voice-project-start.js',
      'voice-local-update.js',
      'voice-microphone-permission.js',
      'voice-playback.js',
      'voice-enhanced-ui.js',
      'voice-chatgpt-layout.js',
      'voice-insecure-lan-guard.js',
      'mobile-voice-capture-final.js',
      'voice-project-autoload.js',
      'mobile-chat-project-picker.js',
      'voice-runtime-stability.js',
      'chat-request-watchdog.js',
    ],
    admin: [
      'super-admin-task-panel.js',
      'token-usage.js',
      'token-usage-mobile-fix.js',
      'deploy-admin.js',
      'cloud-admin.js',
      'super-admin-local-test.js',
      'investia-admin.js',
      'investia-homologation.js',
      'game-rules-admin.js',
      'linux-terminal.js',
      'linux-beginner-coach.js',
      'career-linkedin.js',
      'mission-control.js',
      'rag-admin-ui.js',
      'rag-jobs-ui.js',
    ],
    audit: [
      'audit-integrity.js',
      'telemetry-capture.js',
      'telemetry-replay-capture.js',
    ],
  });

  const critical = Object.freeze({
    shell: bundles.shell,
    mobileShell: bundles.mobileShell,
    profile: bundles.profile,
    users: bundles.users,
    providers: bundles.providers,
    projectBuilder: ['project-provisioning.js', 'project-builder.js', 'project-description-profile.js'],
    projects: ['project-delete-ui.js', 'project-ships.js'],
    taskModal: bundles.taskModal,
    tasks: ['task-modal.js', 'task-analytics.js'],
    reports: ['reports.js'],
    organizations: bundles.organizations,
    example: ['example-project.js'],
    voice: ['super-admin-voice.js', 'voice-project-start.js', 'voice-microphone-permission.js', 'voice-playback.js'],
    admin: ['super-admin-task-panel.js', 'token-usage.js', 'cloud-admin.js', 'rag-admin-ui.js'],
    audit: ['audit-integrity.js'],
  });

  const triggers = Object.freeze([
    {selector: '[data-project-builder-open]', feature: 'projectBuilder'},
    {selector: '[data-example-project]', feature: 'example'},
    {selector: '[data-open="task-modal"], [data-project-task]', feature: 'taskModal'},
    {selector: '.nav[data-view="organizations"]', feature: 'organizations'},
    {selector: '.nav[data-view="projects"]', feature: 'projects'},
    {selector: '.nav[data-view="tasks"]', feature: 'tasks'},
    {selector: '.nav[data-view="providers"]', feature: 'providers'},
    {selector: '.nav[data-view="reports"]', feature: 'reports'},
    {selector: '.nav[data-view="audit"]', feature: 'audit'},
    {selector: '#voice-hero, #voice-dock, #voice-start, #voice-send', feature: 'voice'},
  ]);

  const policies = Object.freeze({
    default: {idleEvery: 3},
    projects: {idleEvery: 2},
    tasks: {idleEvery: 2},
    reports: {idleEvery: 2},
    voice: {idleEvery: 2},
    admin: {idleEvery: 2},
  });

  window.__devpilotRuntimeManifest = Object.freeze({
    version: '20260830-unified-1',
    bundles,
    critical,
    triggers,
    policies,
    routes: Object.freeze({game: '/game/index.html'}),
    requiredFeatures: Object.freeze([
      'shell', 'mobileShell', 'profile', 'users', 'providers', 'projectBuilder',
      'projects', 'taskModal', 'tasks', 'reports', 'organizations', 'example',
      'voice', 'admin', 'audit',
    ]),
  });
})();
