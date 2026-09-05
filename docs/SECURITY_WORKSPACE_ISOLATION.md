# Workspace isolation — authenticated tenant boundary

DevPilot is multi-workspace. For authenticated requests, the workspace carried by the validated session principal is the authoritative tenant boundary.

## Contract

Authenticated routes must not infer tenancy from a conventional workspace slug such as `default`.

Use `app.services.workspace_scope.workspace_for_principal(db, principal)` when a route needs the current `Workspace` row. The helper:

- reads only `principal.workspace_id`;
- performs no fallback to `Workspace.slug == "default"`;
- fails closed with an authentication error when the workspace id is missing or no longer exists.

Queries for projects, tasks, organizations, repositories, provider credentials and audit events must additionally carry the resolved workspace id whenever the model exposes that scope.

Cross-workspace identifiers are treated as not found. An authenticated user must not be able to infer that a project, task, organization or credential exists in another workspace.

## Bootstrap and platform-global paths

The `default` slug may still be used by explicit bootstrap or platform-owned flows whose purpose is to initialize or locate the platform workspace. Such use must not be reused as the tenant resolver for an authenticated request.

## Quality contract

`.devpilot/quality-modules.json` declares a `workspace_isolation` critical module. Its focused tests cover positive access to the principal workspace and negative cross-workspace access.

Any authenticated route newly added to this boundary should be registered in that module and include at least one negative tenant-boundary test.
