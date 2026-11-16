#!/usr/bin/env python3
"""Stage pinned upstream files beside the guide's Kustomize overlays; no cluster writes."""
import argparse
from pathlib import Path
import shutil
import subprocess
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--substrate', type=Path, required=True)
parser.add_argument('--sandbox', type=Path, required=True)
parser.add_argument('--host', default='localhost')
parser.add_argument('--protocol', choices=['http', 'https'], default='http')
args = parser.parse_args()
guide = Path(__file__).resolve().parents[1]
revision = subprocess.check_output(['git', '-C', str(args.substrate), 'rev-parse', 'HEAD'], text=True).strip()
if revision != 'b34fbee742906494b5eb4f1f36987176bf8770a4':
    raise SystemExit('Expected Substrate v1.0.0 source commit')
sandbox_revision = subprocess.check_output(
    ['git', '-C', str(args.sandbox), 'rev-parse', 'HEAD'], text=True).strip()
if sandbox_revision != '564cbf679dbc29a1081a2085fd92779f53527a04':
    raise SystemExit('Expected documented sandbox source commit; review template changes first')
root = args.substrate / 'manifests/ate-install'
# Require both guide patches instead of silently building GKE/GCS defaults.
atelet = (root / 'atelet.yaml').read_text()
if 'value: "s3"' not in atelet or '--image-credential-provider-config=' in atelet:
    raise SystemExit('Apply the generic Kubernetes and S3 patches to Substrate first')
out = guide / '.build/kustomize'
shutil.copytree(guide / 'kustomize', out, dirs_exist_ok=True)

def stage(source, stage_name, filename=None, substitutions=None):
    text = source.read_text()
    for before, after in (substitutions or {}).items():
        text = text.replace(before, after)
    (out / stage_name / (filename or source.name)).write_text(text)

for name in ['ate.dev_csidriverconfigs.yaml', 'ate.dev_sandboxconfigs.yaml',
             'ate.dev_workerpools.yaml', 'role.yaml']:
    stage(root / 'generated' / name, '10-crds')
stage(root / 'sandboxconfig-validation.yaml', '10-crds')
stage(root / 'postgres/postgres.yaml', '20-postgres')
for name in ['ate-api-server.yaml', 'ate-idp-server.yaml', 'ate-controller.yaml',
             'atelet.yaml', 'atenet-router.yaml', 'atenet-egress.yaml',
             'ate-otel-config.yaml', 'ate-system-networkpolicies.yaml',
             'sandboxconfig-gvisor.yaml']:
    stage(root / name, '30-system', substitutions={
        '${ENVOY_DATAPLANE_IMAGE}': 'envoy-dataplane:source'})
stage(args.sandbox / 'substrate/worker-pool.yaml.tmpl', '40-workers', 'worker-pool.yaml', {
    '${SUBSTRATE_WORKER_IMAGE}': 'ghcr.io/agent-substrate/substrate/ateworker-gvisor:v1.0.0@sha256:f8987236c6256f58c4b2625e543b43f4ae4bdded6ee6821c03d966effb7c0f17'})
stage(args.sandbox / 'docs/examples/n8n-app-v1.yaml.tmpl', '50-n8n', 'n8n.yaml', {
    '${N8N_IMAGE}': 'ghcr.io/jseguillon/n8n@sha256:8205a2e0fb5e37e84d0cd7b54e5f21b04e38a4e1009e48f89f103de08a7c6a4c',
    '${N8N_HOST}': args.host, '${N8N_PROTOCOL}': args.protocol})
stage(guide / 'substrate-default-egress.json', '50-n8n')
for source, dest in [('n8n-storage.patch.yaml', 'storage.patch.yaml'),
                     ('n8n-egress-policy.patch.yaml', 'egress.patch.yaml')]:
    patch = yaml.safe_load((guide / source).read_text())
    patch.update(apiVersion='apps/v1', kind='Deployment',
                 metadata={'name': 'n8n', 'namespace': 'n8n-app'})
    (out / '50-n8n' / dest).write_text(yaml.safe_dump(patch))
print(out)
