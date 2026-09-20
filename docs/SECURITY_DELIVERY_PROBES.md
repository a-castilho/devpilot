# Delivery probes — outbound request security

DevPilot validates public deployment URLs before marking a delivery as ready. These requests cross a server-side network boundary and therefore must not follow an unvalidated redirect.

## Contract

Public delivery probes use `app.services.safe_http_probe.probe_public_https_url`.

Every requested hop must:

- use HTTPS;
- use the default HTTPS port (443);
- have no URL credentials/userinfo;
- stay under an approved provider hostname suffix (`*.vercel.app` or `*.onrender.com`);
- resolve only to globally routable IP addresses;
- be validated before the next network request.

Automatic redirects are disabled. Redirects are followed manually for at most three hops, and environment proxy variables are ignored for these probes.

A URL or redirect that resolves to loopback, private, link-local, reserved, multicast or otherwise non-global space fails closed and cannot satisfy the delivery gate.

## Scope

This policy applies to public URL readiness probes in `delivery_url_recovery` and `delivery_cloud_bridge`. Calls to fixed provider API hosts used for provisioning are separate trusted-provider integrations and are not treated as arbitrary public delivery probes.

Any new public URL verification path must reuse the same helper instead of enabling `follow_redirects=True` directly.
