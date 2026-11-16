// Run through kubectl exec -i deployment/n8n -- node - < tests/router-smoke.cjs.
// Requires a resumed guide-smoke Actor with the guide's egress policy.
const fs = require('node:fs');
const https = require('node:https');
const credential = fs.readFileSync(process.env.SUBSTRATE_ROUTER_CREDENTIAL_FILE);
const command = process.env.SMOKE_RESTORE === 'true'
  ? 'test "$(cat /home/user/guide-checkpoint)" = preserved && id'
  : "id && printf preserved > /home/user/guide-checkpoint && python3 -c \"import urllib.request; r=urllib.request.urlopen('https://example.com', timeout=30); print('HTTPS egress:', r.status)\"";
const body = JSON.stringify({command, workdir: '/home/user', timeout_ms: 60000});
const request = https.request(new URL('/executions', process.env.SUBSTRATE_ROUTER_URL), {
  method: 'POST',
  ca: fs.readFileSync(process.env.SUBSTRATE_CA_FILE),
  cert: credential,
  key: credential,
  headers: {'content-type': 'application/json', 'ate-target-actor': 'n8n-sandboxes/guide-smoke'},
}, response => {
  let output = '';
  response.on('data', chunk => { output += chunk; });
  response.on('end', () => {
    console.log('Router HTTP status:', response.statusCode);
    console.log(output);
    if (response.statusCode !== 200 || !output.includes('uid=1000')) process.exitCode = 1;
    const events = output.trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
    if (!events.some(event => event.type === 'exit' && event.exit_code === 0)) process.exitCode = 1;
  });
});
request.setTimeout(90000, () => request.destroy(new Error('Router smoke test timed out')));
request.on('error', error => { console.error(error.message); process.exitCode = 1; });
request.end(body);
