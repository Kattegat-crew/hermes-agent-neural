// OD headless run: create project (with id) + publish DS if needed + POST /api/chat.
// Usage (inside OD container, daemon only answers on 127.0.0.1:7456):
//   docker exec -i -e OD_TOKEN=<token> -e NAN_KEY=<nan-key> open-design node < od_run.js
// The container is read_only -> pass the script on stdin (node < file); do NOT docker cp.
const { randomUUID } = require('node:crypto');
const fs = require('fs');
const T = process.env.OD_TOKEN;      // OD_API_TOKEN from /opt/open-design/.env
const NAN_KEY = process.env.NAN_KEY; // NaN-Builders api_key (read server-side; masked in agent output)
const BASE = 'http://127.0.0.1:7456';

const DS_ID = 'user:neuralcrew-labs';   // must be a PUBLISHED user design system
const AGENT = 'opencode';                // 'openai-api' is the broken default; use 'opencode'

const BRIEF = `Crea una landing page de una sola pantalla para la marca. Una sola pantalla, mobile-first. Usa el design system ${DS_ID}. Todo en espanol.`;

async function publishDS(id) {
  const r = await fetch(`${BASE}/api/design-systems/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${T}` },
    body: JSON.stringify({ published: true }),
  });
  console.log('DS_PUBLISH', id, r.status);
}

async function main() {
  await publishDS(DS_ID); // draft DS -> 400 'DESIGN_SYSTEM_NOT_PUBLISHED' if skipped

  const projId = randomUUID(); // REQUIRED: POST /api/projects rejects with 'invalid project id' without an id
  const create = await fetch(`${BASE}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${T}` },
    body: JSON.stringify({
      id: projId,
      name: 'Landing (API run)',
      designSystemId: DS_ID,
      skillId: null,
      pendingPrompt: BRIEF,
      skipDiscoveryBrief: true,
      metadata: { kind: 'prototype', platform: 'responsive' },
    }),
  });
  console.log('PROJECT_CREATED', create.status, projId);
  if (!create.ok) { console.log('CREATE_BODY', JSON.stringify(await create.json()).slice(0, 300)); return; }

  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${T}` },
    body: JSON.stringify({
      agentId: AGENT,
      message: BRIEF,
      projectId: projId,
      designSystemId: DS_ID,
      sessionMode: 'design',
      byokProvider: { protocol: 'openai', apiKey: NAN_KEY, baseUrl: 'https://api.nan.builders/v1', model: 'deepseek-v4-flash' },
      locale: 'es',
    }),
  });
  console.log('CHAT_STATUS', res.status, res.headers.get('content-type')); // text/event-stream
  const text = await res.text();
  fs.writeFileSync('/tmp/od_chat_stream.txt', text);
  const events = text.split('\n').filter((l) => l.startsWith('data:'));
  for (const l of events.slice(-14)) console.log(l.slice(0, 240));
  // Success = event {type:'runtime_close', status:'succeeded'} with artifactPaths.
  // Artifact at /app/.od/projects/<projectId>/<artifactPaths[0]> (cat it out, container is read_only).
}
main().catch((e) => console.log('FATAL', e.message));
