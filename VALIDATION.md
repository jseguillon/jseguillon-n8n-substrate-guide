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

## Kustomize alternative, 2026-11-16

The Helm release was uninstalled, then the ATE/n8n namespaces, test PVCs,
dedicated RBAC, CRDs and admission policy were removed again. The final install
used the staged `kustomize/` overlays and a new snapshot prefix. ATE workloads,
PostgreSQL, workers and n8n were applied with `kubectl apply -k`; no full-system
installer deployment was used. Signing/config generation used `ate-setup create`,
and database identities used upstream `pkg/postgressetup/setup.sql`.

During testing, raw upstream manifests started ateapi without any bootstrap
owner. Its log reported `--authz-bootstrap-owners must list at least one
principal`. The system overlay now explicitly sets the operator identity. It
also supplies the router SPIFFE allowlist and IDP issuer, which the full
installer normally adds at render time. Namespace labels retain privileged
PodSecurity for atelet. These are required adaptations, not just image changes.

Passed:

- All seven Kustomize stages render. ATE workload images have concrete digests;
  no unresolved `ko://` images remain.
- Server-side dry runs for the system and n8n test overlays.
- PostgreSQL ready with a fresh 10 GiB Longhorn claim; roles initialized.
- ATE API 2/2, IDP 2/2, controller/router/egress 1/1, atelet 1/1.
- Both workers ready and registered active; golden ActorTemplate ready.
- n8n ready with a fresh 2 GiB claim, non-root security context and projected
  token, router identity, CA and operator egress policy.
- Normal login and n8n sandbox verification: HTTP 200, `ok: true`.
- Router smoke test: UID 1000, HTTPS 200, successful synchronous suspend and
  file preservation after resume. The disposable Actor was deleted afterwards.
- Re-staging and `kubectl diff -k` for both system and n8n returned no changes.
- Bootstrap helper re-run preserved all existing Secrets/configs.

Final state: the Kustomize installation remains running. No n8n Helm release
remains. The prior retained 500 GiB PV is still Released/Retain and was never
rebound. The shared certificate controller and kagent remain healthy. Local
Docker applications were not changed. Snapshot storage and host caches were
not purged between installs; each install used a distinct snapshot prefix.

After testing, `n8n user-management:reset` removed the disposable test owner,
and n8n was restarted. `/rest/settings` confirms owner setup is required, so a
new operator can complete normal onboarding. No test password or session is
included in this repository. No LLM-driven conversation was tested.
