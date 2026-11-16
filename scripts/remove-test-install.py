#!/usr/bin/env python3
"""Remove this guide's disposable install, preserving the shared signer and object store."""
import argparse
import json
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--context', required=True)
parser.add_argument('--delete-test-data', action='store_true', required=True,
                    help='acknowledge deletion of n8n-app/ate-system PVCs')
args = parser.parse_args()
k = ['kubectl', '--context', args.context]

def delete(kind, *names, namespace=None):
    command = k + (['-n', namespace] if namespace else [])
    subprocess.run(command + ['delete', kind, *names, '--ignore-not-found',
                              '--timeout=5m'], check=True)

# Deleting WorkerPools while their controller is alive releases SandboxConfigs.
present = subprocess.check_output(k + ['get', 'crd', 'workerpools.ate.dev',
                                       '--ignore-not-found', '-o', 'name']).strip()
if present:
    pools = json.loads(subprocess.check_output(k + ['get', 'workerpools', '-A', '-o', 'json']))
    if any((p['metadata']['namespace'], p['metadata']['name']) !=
           ('n8n-sandboxes', 'n8n-sandbox') for p in pools['items']):
        raise SystemExit('Other WorkerPools exist; refusing shared-system teardown')
    configs = json.loads(subprocess.check_output(k + ['get', 'sandboxconfigs', '-o', 'json']))
    if any(c['metadata']['name'] != 'gvisor-default' for c in configs['items']):
        raise SystemExit('Other SandboxConfigs exist; refusing shared-system teardown')
    delete('workerpool', 'n8n-sandbox', namespace='n8n-sandboxes')
    delete('sandboxconfig', 'gvisor-default')
delete('namespace', 'n8n-app', 'n8n-sandboxes')
delete('namespace', 'ate-system')
delete('clusterrolebinding', 'ate-api-server', 'ate-api-server-binding',
       'ate-controller', 'atelet', 'atelet-binding', 'k8s-credential-provider-secret-reader')
delete('rolebinding', 'ate-prometheus', namespace='otel-system')
delete('clusterrole', 'ate-api-server', 'ate-api-server-role', 'ate-controller',
       'ate-prometheus', 'atelet', 'atelet-role', 'k8s-credential-provider-secret-reader')
delete('validatingadmissionpolicybinding', 'sandboxconfig-assets')
delete('validatingadmissionpolicy', 'sandboxconfig-assets')
delete('crd', 'workerpools.ate.dev', 'sandboxconfigs.ate.dev', 'csidriverconfigs.ate.dev')
delete('clustertrustbundle', 'egress-mitm.ate.dev:mitm:primary-bundle')
print('Removed guide installation; shared podcertificate controller and object store preserved.')
