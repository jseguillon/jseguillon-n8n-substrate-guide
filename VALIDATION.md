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

## Helm alternative, 2026-11-16

The installer deployment was removed, including its new test PVCs, WorkerPool,
CRDs and admission policy. The shared signer and pre-existing retained PV stayed
intact. ATE was then freshly installed with a distinct snapshot prefix.

The existing 8gears n8n chart 2.1.1 rendered successfully with `helm/n8n-values.yaml`
and `helm/test-values.yaml`. `helm upgrade --install --wait` and `helm test`
passed on the remote cluster. The deployed image matched the guide's custom
n8n digest, not the chart's default appVersion.

Normal owner setup/login and authenticated n8n sandbox verification returned
HTTP 200 with `ok: true`. The same router smoke test passed UID 1000, HTTPS
egress and file preservation across synchronous suspend/resume. Restoration
landed on a different worker, confirming it was not just a running process
reading its unchanged local directory. The smoke Actor was deleted afterwards.

Helm coverage is n8n only. No Substrate v1.0.0 Helm chart was introduced, and
the sandbox-service REST/runner chart was not substituted for ATE.
