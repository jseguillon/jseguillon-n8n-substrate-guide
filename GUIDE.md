# Run n8n sandboxes on Agent Substrate v1.0

This guide connects a custom n8n build to Agent Substrate v1.0 on Kubernetes.
It does not depend on Kind or Talos. It uses gVisor workers, a Substrate
ActorTemplate, and the native n8n Substrate client.

Installation paths:

- Sections 1–6: Substrate installer and plain n8n manifests.
- [Helm alternative](#helm-alternative): the same ATE installation plus an
  existing community n8n chart, with tested Substrate values.

## Published images

| Image | Digest-pinned reference | Platform |
| --- | --- | --- |
| n8n 2.48.0 with native Substrate support and rollout gate | `ghcr.io/jseguillon/n8n@sha256:8205a2e0fb5e37e84d0cd7b54e5f21b04e38a4e1009e48f89f103de08a7c6a4c` | linux/amd64 |
| n8n sandbox daemon | `ghcr.io/jseguillon/n8n-sandbox-service-substrate@sha256:223704e6e7b453a6e4473009186fa08b47965858a013d7f063d67f5c33e6b90d` | linux/amd64 |
| Substrate gVisor worker v1.0.0 | `ghcr.io/agent-substrate/substrate/ateworker-gvisor:v1.0.0@sha256:f8987236c6256f58c4b2625e543b43f4ae4bdded6ee6821c03d966effb7c0f17` | linux/amd64, linux/arm64 |

The custom n8n and sandbox images currently have linux/amd64 builds. Schedule
them on amd64 nodes. The worker image supports amd64 and arm64.

The n8n image was built from `feat/substrate-ghcr-publish`. The sandbox image
was built from `feat/substrate-sandbox-build`. Both workflows publish
digest-pinned images to GHCR. Build and test changes on those branches before
you update the image digests in a deployment.

## Requirements

- A Kubernetes cluster and a working `kubectl` context.
- Go 1.27.3 or later, Git, and `envsubst` to run the Substrate v1.0.0 installer
  and apply the deployment templates.
- A gVisor runtime and an object store for snapshots.
- Kubernetes support for the `PodCertificate` and `ClusterTrustBundle`
  projections used below. Enable the required Kubernetes certificate API
  features if the cluster does not serve them by default.
- Permission to run Substrate's `atelet` and WorkerPool hostPath workloads.
  The `ate-system` and worker namespaces need Pod Security Admission level
  `privileged`. Keep the n8n application namespace at its normal security level.
- Access to pull the three container images in the table above.

Substrate v1 uses two identities for n8n. The Control API uses a bearer token.
The router uses a PodIdentity client certificate. The token does not replace the
router certificate.

## 1. Get the deployment files

Start in an empty working directory. Keep all three repositories side by side.
Pin the Kubernetes context for the entire procedure, including `kubectl ate`:

```sh
export KUBECTL_CONTEXT='<remote-context>'
kubectl config use-context "$KUBECTL_CONTEXT"
git clone --branch docs/substrate-default-egress \
  https://github.com/jseguillon/jseguillon-n8n-substrate-guide.git
export GUIDE_DIR="$PWD/jseguillon-n8n-substrate-guide"
git clone --branch v1.0.0 https://github.com/agent-substrate/substrate.git
git clone --branch feat/substrate-sandbox-build \
  https://github.com/jseguillon/n8n-sandbox-service-substrate.git
```

The v1.0.0 installer includes GKE-specific resources in its generic manifest
set. Apply this compatibility patch to the pinned Substrate checkout. It removes
the GKE Managed Prometheus resource and GKE-only kubelet image-credential mounts.
It also labels `ate-system` for the required PodSecurity level.

```sh
git -C substrate apply \
  ../n8n-sandbox-service-substrate/docs/examples/substrate-v1.0.0-generic-k8s.patch
```

The patch keeps the public GHCR images in this guide usable. It removes the
GKE-specific image credential provider flags and hostPath mounts. For private
Actor registries, add the correct credential-provider configuration for your
cluster to the `atelet` DaemonSet.

The bundled PostgreSQL requests a **500 GiB PVC**, 2 CPUs and 1 GiB memory.
The two workers request another 16 GiB memory and 2 CPUs. Check available
capacity and the default StorageClass before proceeding. For a small test
installation, change `storage: 500Gi` in
`substrate/manifests/ate-install/postgres/postgres.yaml` before the first deploy;
the installer has a StorageClass flag but no volume-size flag. Existing PVCs
cannot be shrunk. gVisor is supplied through Substrate's SandboxConfig assets;
this path does not require a Kubernetes `RuntimeClass` named `gvisor`.

If `podcertificate-controller-system` already serves another application,
preserve its signer pools, trust bundles and controller during installation
and cleanup. Do not use the upstream whole-system delete command in that case.

Create the Substrate namespace and operator identity before you add storage
settings or install the control plane:

```sh
kubectl create namespace ate-system --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace ate-system \
  pod-security.kubernetes.io/enforce=privileged --overwrite
kubectl create serviceaccount ate-operator -n ate-system \
  --dry-run=client -o yaml | kubectl apply -f -
```

## 2. Choose snapshot storage

Create the bucket before installing Substrate. Keep snapshots private. Allow the
Substrate snapshot components to read, write, list, and delete objects. Do not
give snapshot credentials to sandbox Actors.

### GCS

Use the upstream GCS object-store plugin. Configure a Google service account
that can access the snapshot bucket. Configure the cluster so the Substrate
pods can use that identity.

```sh
export GCP_PROJECT_ID='<project-id>'
export SNAPSHOT_TRANSFER_GSA_NAME='<transfer-service-account-name>'
export SNAPSHOT_LOCATION='gs://<bucket>/<prefix>/'
```

The transfer service account needs the permissions in Substrate's
[snapshot-storage guide](https://github.com/agent-substrate/substrate/blob/v1.0.0/docs/guides/operator-install.md#snapshot-storage).

### S3-compatible storage

Substrate v1.0.0 includes an S3 object-store plugin, but its non-Kind installer
does not expose an S3 backend option. Apply the S3 manifest patch before you
deploy Substrate. The patch makes both object-store sidecars read their endpoint
settings from a ConfigMap and their credentials from a Secret.

```sh
git -C substrate apply \
  ../n8n-sandbox-service-substrate/docs/examples/substrate-v1.0.0-s3.patch

export S3_REGION='<region>'
export S3_ENDPOINT='https://<s3-endpoint>'
envsubst '${S3_REGION} ${S3_ENDPOINT}' \
  < n8n-sandbox-service-substrate/docs/examples/substrate-v1.0.0-s3-config.yaml.tmpl \
  | kubectl apply -f -
```

Put the access key and secret key in protected files. Create the Kubernetes
Secret without printing either value:

```sh
kubectl -n ate-system create secret generic substrate-s3-credentials \
  --from-file=AWS_ACCESS_KEY_ID=/secure/path/access-key \
  --from-file=AWS_SECRET_ACCESS_KEY=/secure/path/secret-key \
  --dry-run=client -o yaml | kubectl apply -f -
export SNAPSHOT_LOCATION='s3://<bucket>/<prefix>/'
```

The v1.0.0 installer still requires the GCS transfer-account settings on a
non-Kind install, even with the S3 patch. S3 does not use those values. Set
placeholders to pass that installer preflight:

```sh
export GCP_PROJECT_ID='unused-for-s3'
export SNAPSHOT_TRANSFER_GSA_NAME='unused-for-s3'
```

## 3. Install Substrate v1.0.0

Install the v1.0.0 control plane. Set `SNAPSHOT_LOCATION` and the storage
settings from the section above first.

```sh
cd substrate
go install ./cmd/kubectl-ate
export PATH="$(go env GOPATH)/bin:$PATH"
export ATE_CLIENT_SERVICE_ACCOUNT=ate-operator

go run ./cmd/ate-setup \
  --image-repo ghcr.io/agent-substrate/substrate \
  --image-tag v1.0.0 \
  --rollout-timeout=5m \
  --credential-provider='{"enabled":false}' \
  --sandbox-classes=gvisor \
  --ateapi-authz-bootstrap-owners=system:serviceaccount:ate-system:ate-operator \
  --ingress-allowed-spiffe-ids=spiffe://cluster.local/ns/n8n-app/sa/n8n \
  --snapshot-location="$SNAPSHOT_LOCATION" \
  --gcp-project-id="$GCP_PROJECT_ID" \
  --snapshot-transfer-gsa-name="$SNAPSHOT_TRANSFER_GSA_NAME" \
  deploy ate-system
```

The router allowlist permits the n8n service identity to reach Actors. Each
listed identity can reach any Actor in this Substrate install. Keep it limited
to trusted n8n server workloads. The default-deny egress credential provider is
disabled here because the sample does not inject Kubernetes Secrets into Actors.

Check the control plane and gVisor default:

```sh
kubectl -n ate-system rollout status deployment/ate-api-server
kubectl -n ate-system rollout status daemonset/atelet
kubectl get sandboxconfigs
```

Before creating API resources, check authenticated access:

```sh
kubectl ate get atespaces
```

On a cluster whose Kubernetes issuer uses a private CA or authenticated discovery
(including the tested Talos cluster), a Ready API server can still reject this
call with `Unauthenticated: invalid bearer token`. Configure the Kubernetes JWT
provider with the existing projected Kubernetes CA and token, then restart the
API server. Python 3 and PyYAML are required for this helper:

```sh
python3 "$GUIDE_DIR/scripts/configure-kubernetes-jwt.py" --context "$KUBECTL_CONTEXT"
kubectl ate get atespaces
```

The helper preserves other providers and keeps TLS verification enabled. It
references `/var/run/secrets/kubernetes.io/serviceaccount/{ca.crt,token}`; it
does not copy a token into a ConfigMap. See the
[authentication guide](https://github.com/agent-substrate/substrate/blob/v1.0.0/docs/guides/authentication.md).

## 4. Deploy the n8n WorkerPool and ActorTemplate

```sh
export SUBSTRATE_WORKER_IMAGE='ghcr.io/agent-substrate/substrate/ateworker-gvisor:v1.0.0@sha256:f8987236c6256f58c4b2625e543b43f4ae4bdded6ee6821c03d966effb7c0f17'
export SUBSTRATE_SANDBOX_IMAGE='ghcr.io/jseguillon/n8n-sandbox-service-substrate@sha256:223704e6e7b453a6e4473009186fa08b47965858a013d7f063d67f5c33e6b90d'

cd ../n8n-sandbox-service-substrate
envsubst '${SUBSTRATE_WORKER_IMAGE}' < substrate/worker-pool.yaml.tmpl \
  | kubectl apply -f -
kubectl -n n8n-sandboxes rollout status deployment/n8n-sandbox --timeout=5m

kubectl ate create atespace n8n-sandboxes
kubectl ate create access-policy -a n8n-sandboxes -f - <<'YAML'
metadata:
  name: default
bindings:
- role: editor
  members:
  - user:system:serviceaccount:n8n-app:n8n
YAML

envsubst '${SUBSTRATE_SANDBOX_IMAGE}' < substrate/actor-template.yaml.tmpl \
  | kubectl ate create actor-template -f -
kubectl ate get actor-template n8n-sandbox -a n8n-sandboxes
```

Wait for a non-empty `GOLDEN TAG` and an empty `ERROR` column before you install
n8n. The template listens on port 80, which is Substrate's default HTTP actor
port. It grants only `NET_BIND_SERVICE` to bind that port.

The WorkerPool namespace is labeled `privileged` because Substrate workers need
hostPath access. Do not run untrusted workloads in this namespace.

Pod readiness does not prove both workers registered. Run `kubectl ate get workers`
and check both are active. The first template build also downloads the Actor
image into atelet's separate cache; a cached Kubernetes image does not skip it.
On the tested cluster this took about four minutes. Inspect atelet logs and
repeat the template query until `GOLDEN TAG` appears.

## 5. Install the custom n8n image

The n8n image includes the v1 Substrate client. The example manifest projects a
short-lived ServiceAccount token for the Control API and a PodIdentity
certificate for router mTLS.

Set `GUIDE_DIR` to the directory that contains this guide and its companion
policy and patch files. Create the default-policy ConfigMap before installing
n8n:

```sh
kubectl create namespace n8n-app --dry-run=client -o yaml | kubectl apply -f -
kubectl -n n8n-app create configmap n8n-substrate-default-egress \
  --from-file=default.json="$GUIDE_DIR/substrate-default-egress.json" \
  --dry-run=client -o yaml | kubectl apply -f -
```

```sh
export N8N_IMAGE='ghcr.io/jseguillon/n8n@sha256:8205a2e0fb5e37e84d0cd7b54e5f21b04e38a4e1009e48f89f103de08a7c6a4c'
export N8N_HOST='<n8n-hostname>'
export N8N_PROTOCOL='https'
envsubst '${N8N_IMAGE} ${N8N_HOST} ${N8N_PROTOCOL}' \
  < docs/examples/n8n-app-v1.yaml.tmpl \
  | kubectl apply -f -
kubectl -n n8n-app patch deployment n8n --type=strategic \
  --patch-file "$GUIDE_DIR/n8n-storage.patch.yaml"
kubectl -n n8n-app patch deployment n8n --type=strategic \
  --patch-file "$GUIDE_DIR/n8n-egress-policy.patch.yaml"
kubectl -n n8n-app rollout status deployment/n8n --timeout=5m
```

The storage patch is required on provisioners that create root-owned volumes
(tested with Longhorn). Without `fsGroup: 1000`, n8n exits with
`EACCES: permission denied, open '/home/node/.n8n/config'`. It also uses Recreate
for the single SQLite/RWO instance and pins these amd64-only images to amd64.

The example creates a ClusterIP Service. Expose it through your ingress, or use
`kubectl -n n8n-app port-forward svc/n8n 5678:5678` for local testing. Set
`N8N_HOST` and `N8N_PROTOCOL` to match the URL you use.

For a loopback-only HTTP port-forward test, set `N8N_HOST=localhost` and
`N8N_PROTOCOL=http` before rendering, and set `N8N_SECURE_COOKIE=false` on the
deployment. Use secure cookies with HTTPS for externally accessible installs.

The provider stays unavailable until PostHog flag `140_substrate_sandbox` is
enabled for the user. Create the flag disabled in Staging and Production before
rollout. For isolated development or testing, force-enable the flag with:

```sh
kubectl -n n8n-app set env deployment/n8n N8N_SUBSTRATE_SANDBOX_ENABLED=true
kubectl -n n8n-app rollout status deployment/n8n --timeout=5m
```

Do not set this override to manage a production rollout. Use PostHog enrolment.

The `n8n-app` namespace uses `ate.dev/api-access=true` so its pod can call the
Substrate Control API. Its ServiceAccount is an editor only in `n8n-sandboxes`.
The projected PodIdentity certificate identifies the same ServiceAccount to
`atenet-router`. `SUBSTRATE_CA_FILE` trusts the service DNS certificates. The
client reloads the router credential bundle when the certificate rotates.

Open the n8n URL and complete owner setup. Configure a supported LLM in n8n if
you want to run an Assistant test. Do not put API keys in the image or manifest.

### Default Actor egress policy

The Kubernetes ConfigMap `n8n-substrate-default-egress` provides
`/run/substrate-egress/default.json` inside the n8n container. The deployment
sets `SUBSTRATE_EGRESS_POLICY_FILE` to that read-only mounted file. The policy is
operator configuration, not a built-in allowlist in n8n code.

The companion `substrate-default-egress.json` selects all destination hostnames:

```json
{
  "rules": [
    { "http": { "hostnames": ["*"], "ports": { "numbers": [80] } } },
    { "tlsPassthrough": { "hostnames": ["*"], "ports": { "all": {} } } }
  ]
}
```

This permits cleartext HTTP on port 80 and TLS passthrough on the remaining
ports, including HTTPS on 443. The explicit HTTP port takes precedence over
the all-port TLS rule. Substrate rejects rules that allow both protocols for
the same hostname pattern on all ports because the rules tie.

This is broad HTTP/TLS access, not unrestricted IP networking. Substrate v1
does not support arbitrary TCP, UDP, TLS without SNI, STARTTLS, or server-first
protocols through its egress policies. Cleartext HTTP on other ports also needs
an explicit HTTP rule. Policies cannot remove those platform limits.

n8n validates the file before acquiring an Actor. It copies the rules to the
Actor's `default` egress policy before resume if no policy exists. It leaves
existing Actor policies unchanged. New Actors do not inherit the template's
golden egress policy. With `SUBSTRATE_EGRESS_POLICY_FILE` unset, n8n makes no
egress-policy calls.

To change the default, edit `substrate-default-egress.json` and repeat the
ConfigMap command above. The mount uses a directory rather than `subPath`, so
Kubernetes eventually projects ConfigMap updates into running Pods. Restart n8n
to make the change available immediately:

```sh
kubectl -n n8n-app rollout restart deployment/n8n
kubectl -n n8n-app rollout status deployment/n8n --timeout=5m
kubectl -n n8n-app exec deployment/n8n -c n8n -- \
  sh -c 'cat "$SUBSTRATE_EGRESS_POLICY_FILE"'
```

File changes affect new Actors and Actors without a policy. To replace a policy
on an existing Actor, use the Substrate policy API or CLI explicitly.

## 6. Verify an n8n sandbox

Open **Agents → Assistant**, start a chat, and ask it to run `id` in the code
sandbox. The result should include `uid=1000(user)`. The Assistant workspace is
an Actor in `n8n-sandboxes`:

```sh
kubectl ate get actors -a n8n-sandboxes
kubectl ate get actor-template n8n-sandbox -a n8n-sandboxes
```

n8n records command and file-operation leases. When automatic suspension is
enabled, the final operation starts a five-second grace period by default.
New activity cancels pending suspension. An hourly recovery task handles missed
cleanup and Actor retention. For a manual synchronous snapshot:

```sh
kubectl ate suspend actor <actor-name> -a n8n-sandboxes --mode=sync
```

Use a v1.0.0 `kubectl-ate` binary from the Agent Substrate release. An older CLI
calls `ateapi.Control` instead of `substrate.ateapi.v1.Control` and fails with
`Unimplemented: unknown service ateapi.Control`. The egress policy applies to
one Actor. n8n copies the configured default to Actors that do not have an
existing policy.

### Identity and router notes

- **Control API:** n8n reads `SUBSTRATE_TOKEN_FILE` for each gRPC call. The
  token audience is `api.ate-system.svc`. You can use another JWT issuer if
  ate-api-server trusts it and an Atespace access policy grants the principal
  the required role.
- **Router:** HTTPS requests use the projected PodIdentity bundle in
  `SUBSTRATE_ROUTER_CREDENTIAL_FILE`. The router checks its SPIFFE ID against
  `--ingress-allowed-spiffe-ids`.
- **External n8n:** A ServiceAccount token can authenticate to the Control API
  when its issuer is configured. It does not authenticate to the router. Use a
  valid Substrate-trusted client certificate or a private policy-enforcement
  proxy that authenticates clients and overwrites `ate-target-actor`.
- **Private actor registry:** The generic patch removes GKE-specific kubelet
  image-credential paths. Configure your cluster's image credential provider
  before using private Actor images. The images in this guide are public GHCR
  references.

## 7. Repeatable sandbox smoke test

After normal n8n owner setup, use the settings UI's sandbox verification, or
call authenticated `POST /rest/assistant/settings/verify/sandbox` with
`{"provider":"substrate"}`. Session requests require both the login cookie and
the browser's `browser-id` header. A 401 here does not prove ATE failed.

The following independent test checks UID, HTTPS egress and snapshot restoration
through the n8n pod's real router identity. The name `guide-smoke` must be unused:

```sh
kubectl ate create actor guide-smoke -a n8n-sandboxes --template n8n-sandbox
kubectl ate create egress-policy guide-smoke -a n8n-sandboxes \
  -f "$GUIDE_DIR/substrate-default-egress.json"
kubectl ate resume actor guide-smoke -a n8n-sandboxes
kubectl -n n8n-app exec -i deployment/n8n -- node - < "$GUIDE_DIR/tests/router-smoke.cjs"
kubectl ate suspend actor guide-smoke -a n8n-sandboxes --mode=sync
kubectl ate resume actor guide-smoke -a n8n-sandboxes
kubectl -n n8n-app exec -i deployment/n8n -- env SMOKE_RESTORE=true node - \
  < "$GUIDE_DIR/tests/router-smoke.cjs"
kubectl ate delete actor guide-smoke -a n8n-sandboxes
```

See [VALIDATION.md](VALIDATION.md) for observed results and limits.

## 8. Remove a disposable installation

For the fixed namespaces and resource names used in this guide, the helper
removes workers while their controller can release SandboxConfig protection,
then namespaces, dedicated RBAC, admission policy and CRDs. It keeps the
shared podcertificate controller, its trust bundles, object storage and
node-local caches. It is intended for a dedicated guide test install, with no
other WorkerPools or SandboxConfigs. Inspect existing resources first.

**This deletes the n8n and ATE PVCs and data when their PV reclaim policy is
Delete.** Back up data or set those PVs to Retain before using it on an install
you need to keep. Do not run it on another Substrate user's installation.

```sh
python3 "$GUIDE_DIR/scripts/remove-test-install.py" \
  --context "$KUBECTL_CONTEXT" --delete-test-data
kubectl get ns ate-system n8n-sandboxes n8n-app --ignore-not-found
```

If n8n was installed with Helm, uninstall that release before running this
helper. An upstream `ate-setup delete ate-system` also deletes the certificate
controller and its trust bundles; use it only when no other application uses
those signers.

## Helm alternative

Substrate v1.0.0 does not ship a Helm chart. Use sections 1–4 for ATE, workers
and API resources, including the generic/S3 patches and JWT discovery fix.
There is no claim that Helm manages ATE here.

For n8n, the existing community [8gears chart](https://github.com/8gears/n8n-helm-chart)
supports the projected identities and extra environment/volumes needed by this
provider. Chart **2.1.1** was tested; its OCI digest was
`sha256:ac5e38f96b91bb39539a0e1647d5f390b8aadf6c03f706e61acfd783b03a6217`.
The chart's default app version is overridden with the guide's custom
digest-pinned n8n 2.48.0 image. Do not install the sandbox-service chart from the
sandbox repository: it deploys the REST API/runner service, not native ATE.

Replace section 5 with these commands. Do not apply the plain n8n manifest to
the same namespace/release. Start after removing any earlier guide install:

```sh
kubectl create namespace n8n-app --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace n8n-app ate.dev/api-access=true --overwrite
kubectl -n n8n-app create configmap n8n-substrate-default-egress \
  --from-file=default.json="$GUIDE_DIR/substrate-default-egress.json" \
  --dry-run=client -o yaml | kubectl apply -f -
helm template n8n oci://8gears.container-registry.com/library/n8n \
  --version 2.1.1 --namespace n8n-app \
  -f "$GUIDE_DIR/helm/n8n-values.yaml" -f "$GUIDE_DIR/helm/test-values.yaml"
helm upgrade --install n8n oci://8gears.container-registry.com/library/n8n \
  --version 2.1.1 --kube-context "$KUBECTL_CONTEXT" --namespace n8n-app \
  -f "$GUIDE_DIR/helm/n8n-values.yaml" -f "$GUIDE_DIR/helm/test-values.yaml" \
  --wait --timeout 5m
helm test n8n --kube-context "$KUBECTL_CONTEXT" --namespace n8n-app --timeout 2m
kubectl -n n8n-app port-forward svc/n8n 5678:5678
```

These are loopback HTTP test values. For an externally reachable installation,
omit `test-values.yaml`, override `main.extraEnv.N8N_HOST.value` and
`main.extraEnv.N8N_PROTOCOL.value` for your HTTPS endpoint, configure ingress/TLS
and enrol users through PostHog. The base values keep the ServiceAccount named
`n8n`, matching both the ATE access policy and router SPIFFE allowlist.

Complete owner setup and repeat sections 6–7. `helm test` checks only Service
reachability; it does not check ATE. After testing, remove the Helm release
and then the remaining ATE test installation:

```sh
helm uninstall n8n --kube-context "$KUBECTL_CONTEXT" --namespace n8n-app --wait
python3 "$GUIDE_DIR/scripts/remove-test-install.py" \
  --context "$KUBECTL_CONTEXT" --delete-test-data
```
