#!/usr/bin/env python3
"""Configure private Kubernetes OIDC discovery without disabling TLS verification."""
import argparse
import json
import subprocess
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--context', required=True)
args = parser.parse_args()
kubectl = ['kubectl', '--context', args.context, '-n', 'ate-system']
config = json.loads(subprocess.check_output(
    kubectl + ['get', 'configmap', 'ate-api-authentication', '-o', 'json']))
authentication = yaml.safe_load(config['data']['authentication.yaml'])
provider = next(p for p in authentication['jwtProviders'] if p['name'] == 'kubernetes')
provider['certificateAuthorityFile'] = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
provider['discoveryTokenFile'] = '/var/run/secrets/kubernetes.io/serviceaccount/token'
patch = {'data': {'authentication.yaml': yaml.safe_dump(authentication)}}
subprocess.run(kubectl + ['patch', 'configmap', 'ate-api-authentication',
                         '--type=merge', '--patch', json.dumps(patch)], check=True)
subprocess.run(kubectl + ['rollout', 'restart', 'deployment/ate-api-server'], check=True)
subprocess.run(kubectl + ['rollout', 'status', 'deployment/ate-api-server',
                         '--timeout=5m'], check=True)
