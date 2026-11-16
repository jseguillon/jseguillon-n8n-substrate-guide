# Remote installation validation

## Installer path, 2026-11-16

Tested on a remote Talos v1.14.0 / Kubernetes v1.37.0 amd64 cluster with
Longhorn and an existing RustFS service. Sources:

- Substrate v1.0.0: `b34fbee742906494b5eb4f1f36987176bf8770a4`.
- Sandbox fork: `564cbf6` (`feat/substrate-sandbox-build`).
- n8n, sandbox and worker image digests: the Published images table in GUIDE.

The snapshot bucket was created exclusively for these tests. No pre-existing
database or snapshot bucket was reused. The existing podcertificate controller
also serves kagent, so its signer pools and controller were preserved.

Checks passed after applying the documented fixes:

- All ATE workloads ready; both workers registered `WORKER_STATE_ACTIVE`.
- ActorTemplate has a golden tag and no error. First image pull took 255 seconds.
- n8n runs as UID 1000 and passes HTTP health checks on a new Longhorn PVC.
- Normal owner login with a browser-id header, followed by authenticated
  `POST /rest/assistant/settings/verify/sandbox` with `{"provider":"substrate"}`:
  HTTP 200, `ok: true`. This exercises native lifecycle, router execution and
  filesystem write/read/delete without an LLM or paid API credential.
- A disposable `guide-smoke` Actor returned `uid=1000(user)` through router mTLS.
- HTTPS egress to example.com returned 200 with the guide's default policy.
- Synchronous suspend completed; resume preserved a file containing `preserved`.
- Disposable Actors were deleted; the atespace actor list was empty afterwards.

Confirmed guide gaps: cloning/path setup, private Kubernetes OIDC discovery,
n8n PVC permissions, single-instance update strategy, and PostgreSQL capacity.
The guide now includes the tested fixes. A missing OTLP collector causes
telemetry export warnings; an observability installation is not included.

An LLM-driven Assistant conversation has not been tested. The checks above
exercise sandbox plumbing through the actual n8n verification endpoint and a
separate Actor; they do not establish model tool-selection behavior.
