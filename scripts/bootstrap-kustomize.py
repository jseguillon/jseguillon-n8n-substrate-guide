#!/usr/bin/env python3
"""Create missing ATE key material and server config for the S3 Kustomize path."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--context', required=True)
parser.add_argument('--substrate', type=Path, required=True)
parser.add_argument('--ate-setup', type=Path, required=True)
parser.add_argument('--snapshot-location', required=True)
args = parser.parse_args()
if not args.snapshot_location.startswith('s3://'):
    raise SystemExit('This overlay requires the documented S3 backend')
base = [str(args.ate_setup.resolve()), '--context', args.context, '--no-dev-env',
        '--snapshot-location', args.snapshot_location,
        '--gcp-project-id=unused-for-s3', '--snapshot-transfer-gsa-name=unused-for-s3',
        '--no-report-defaults']
k = ['kubectl', '--context', args.context, '-n', 'ate-system']
resources = [
    ('secret', 'actor-id-jwt-pool', 'jwt-authority-pool'),
    ('secret', 'actor-id-ca-pool', 'actor-id-ca-pool'),
    ('secret', 'actor-id-ca-certs', 'actor-id-ca-certs'),
    ('secret', 'egress-mitm-ca-pool', 'egress-mitm-ca-pool'),
    ('configmap', 'ate-api-server-envvars', 'api-server-env-vars'),
    ('configmap', 'ate-api-config', 'api-config'),
    ('configmap', 'ate-api-authentication', 'api-authentication-config'),
]
for kind, name, command in resources:
    exists = subprocess.check_output(k + ['get', kind, name, '--ignore-not-found', '-o', 'name']).strip()
    if exists:
        print(f'Preserving {kind}/{name}', flush=True)
    else:
        subprocess.run(base + ['create', command], cwd=args.substrate, check=True)
