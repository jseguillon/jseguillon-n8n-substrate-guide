# Agent instructions: new Agent Substrate + n8n POC

Your role is to guide the user through a real, fresh proof-of-concept installation
of Agent Substrate (ATE) and its native n8n integration. Follow this order:
**read the guide → ask questions → audit → plan → obtain confirmation → deploy
and verify**. Do not start installing or changing infrastructure before the user
confirms the plan.

## 1. Read the online guide

Before advising on deployment, read the online installation guide and the local
`README.md`:

- [Installation guide on GitHub](https://github.com/jseguillon/jseguillon-n8n-substrate-guide/blob/main/README.md)
- [Guide repository and deployment files](https://github.com/jseguillon/jseguillon-n8n-substrate-guide)
- [Upstream Agent Substrate v1.0.0 operator guide](https://github.com/agent-substrate/substrate/blob/v1.0.0/docs/guides/operator-install.md)

Follow the guide's pinned versions, prerequisites, compatibility patches, and
authentication requirements. If the online guide is unavailable, tell the user
and ask whether to proceed using the local copy. Resolve differences between the
online guide and the checked-out revision before preparing deployment commands.

## 2. Ask the user first

Collect and confirm these choices before auditing the environment. Reuse answers
the user already supplied; ask follow-up questions for missing or ambiguous details.

1. **Where should n8n run?** Local Docker or a Kubernetes cluster?
2. **Which Kubernetes cluster should host Agent Substrate (ATE)?** ATE must run
   on Kubernetes, including when n8n runs in local Docker.
   - Reuse an existing cluster, or deploy a new dedicated cluster for this POC?
   - For an existing cluster, ask for its distribution/provider and exact
     `kubectl` context. For a new cluster, ask where to provision it, the desired
     distribution/provider, and the available compute and storage resources.
3. **If n8n runs in Docker, which Docker environment should be used?**
   - Reuse an existing local Docker Engine/context, or set up a dedicated Docker
     environment for the POC? Clarify whether dedicated means an isolated Compose
     project on the existing engine or a separate host/VM and engine.
   - Confirm the target host/context, available ports, and persistence location.
4. **If n8n runs in Kubernetes, which cluster should host it?**
   - The same cluster as ATE or a separate cluster?
   - Reuse an existing cluster or deploy a dedicated one? Confirm its context or
     provisioning details separately if it differs from ATE's cluster.
5. **If n8n runs in Kubernetes, how should the user access it?** Ask explicitly
   whether to use **port-forwarding** or an **`xip.io` address**.
   - For port-forwarding, confirm the local port and host from which it will run.
   - For `xip.io`, confirm the reachable IP address, ingress controller or other
     routing mechanism, and HTTP/HTTPS requirements. A DNS name alone does not
     provide ingress or network reachability.
6. **Which snapshot object-storage backend should this POC use: S3-compatible
   storage or GCS?** Ask whether to reuse an existing service or provision one.
   - For an existing service, confirm the endpoint or GCS project, bucket/prefix,
     region where applicable, and identity or secret references.
   - If S3-compatible storage is needed, ask explicitly whether to deploy it in a
     Kubernetes cluster and which implementation the user wants: **RustFS or
     another S3-compatible service**. Do not select an implementation implicitly.
   - For a new in-cluster service, confirm the target cluster/context, namespace,
     version, persistent storage capacity and StorageClass, resource budget, and
     endpoint/TLS requirements. Confirm bucket creation and credential management.
   - For GCS, confirm whether the bucket and workload identity already exist or
     need provisioning, and in which project and location.
7. **What resources should this POC use?** Confirm namespaces/project names,
   application storage, resource budget, and any network or access constraints. Ask for secret
   references or protected files rather than credentials in chat.

Summarize the answers and resolve open choices with the user. Do not infer a
deployment target from whichever Docker or Kubernetes context happens to be active.

## 3. Audit the agreed environment

After the user has supplied the choices, perform a read-only audit against those
answers. Check the intended existing targets and, for new infrastructure, the
host/provider prerequisites and capacity needed to provision it. Do not create
clusters, install tools, or modify workloads during this audit.

Check at least:

- Available tools and versions required by the selected guide installation path.
- Exact Kubernetes and Docker contexts, connectivity, and permissions.
- Kubernetes version and certificate API feature support, node architecture,
  gVisor/hostPath compatibility, and required Pod Security settings.
- CPU, memory, storage capacity, StorageClasses, and persistence requirements,
  including the guide's default PostgreSQL PVC and worker resource requests.
- Image availability and architecture compatibility with the pinned n8n, sandbox,
  and worker images.
- Compatibility of the chosen S3-compatible or GCS backend with the guide's
  snapshot plugins, authentication, endpoint/TLS settings, and required patches.
  For an existing service, check access without changing objects. For a proposed
  in-cluster service, check implementation prerequisites, image architecture,
  storage capacity, and connectivity requirements; identify checks that must wait
  until deployment.
- Connectivity from the chosen n8n runtime to ATE's Control API and router,
  including bearer-token and PodIdentity certificate requirements.
- Available local ports or `xip.io` DNS resolution, IP reachability, and ingress
  prerequisites, depending on the selected exposure method.
- Existing installations, namespaces, ports, and shared certificate-controller
  resources that could conflict with or be affected by the POC.

Report what matches the user's choices, any incompatibilities, and anything that
could not be verified. Ask the user to resolve blockers or approve revised choices;
do not silently switch targets, exposure methods, or installation paths. If a
requested topology lacks instructions in the guide, identify that gap and explain
the proposed adaptation in the plan.

## 4. Present a plan and wait for confirmation

Prepare a concrete plan based on the confirmed answers and audit. Include:

- The target hosts, explicit contexts, namespaces, and Docker project if used.
- Infrastructure to provision versus existing resources to reuse.
- The chosen installation path, pinned versions, and compatibility changes.
- Deployment steps for storage, ATE, n8n, credentials, and network connectivity.
- The selected snapshot backend and any new object-store deployment, including
  the user-selected S3 implementation (RustFS or another), pinned version,
  persistence, bucket setup, authentication, and snapshot read/write validation.
- The selected access method and expected n8n URL or port-forward command.
- Validation steps proving n8n can run a sandbox through Substrate.
- A cleanup procedure scoped to resources created for this POC.

Ask the user to explicitly confirm this plan, then **wait for their answer**.
Answers to the initial questions are not approval to deploy. If the plan changes
materially after approval, explain the changes and obtain renewed confirmation.

## 5. Deploy and verify

Only after explicit confirmation, execute the approved plan using the agreed
targets and explicit contexts. Preserve existing resources and keep credentials
out of source files and output. Validate readiness, the selected n8n access path,
and an actual n8n-to-Substrate sandbox execution. Report the deployed resources,
access instructions, verification results, and any remaining blockers. Do not
claim a working POC until the end-to-end integration has been verified.
