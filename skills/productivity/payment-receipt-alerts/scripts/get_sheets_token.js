const crypto = require('crypto');
const https = require('https');
const cp = require('child_process');

const tenant = process.argv[2] || 'golden';
const connIds = {
  lucky: 'qSQs2cY927uiPDudu9qtj',
  golden: 'TEd5XvMY397uFjXL4iGRu'
};

const connId = connIds[tenant] || connIds.golden;
const key = 'd0d965cde2b91da7871afb16a9fe2717';

function decrypt(val) {
  const iv = Buffer.from(val.iv, 'hex');
  const data = Buffer.from(val.data, 'hex');
  const decipher = crypto.createDecipheriv('aes-256-cbc', Buffer.from(key), iv);
  let decrypted = decipher.update(data);
  return JSON.parse(Buffer.concat([decrypted, decipher.final()]).toString());
}

try {
  const raw = cp.execSync(`docker exec ap-db psql -U postgres -d activepieces -t -A -c "SELECT value FROM app_connection WHERE id = '${connId}'"`).toString();
  const dec = decrypt(JSON.parse(raw));

  const reqBody = JSON.stringify({
    refreshToken: dec.refresh_token,
    pieceName: '@activepieces/piece-google-sheets',
    clientId: dec.client_id,
    edition: 'COMMUNITY',
    authorizationMethod: dec.authorization_method,
    tokenUrl: dec.token_url
  });

  const req = https.request('https://secrets.activepieces.com/refresh', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(reqBody)
    }
  }, (res) => {
    let body = '';
    res.on('data', chunk => body += chunk);
    res.on('end', () => {
      try {
        const data = JSON.parse(body);
        if (data.access_token) {
          process.stdout.write(data.access_token);
        } else {
          process.stderr.write('No access token in response: ' + body);
          process.exit(1);
        }
      } catch (e) {
        process.stderr.write('JSON parse error: ' + e.message);
        process.exit(1);
      }
    });
  });

  req.on('error', (e) => {
    process.stderr.write('HTTP error: ' + e.message);
    process.exit(1);
  });

  req.write(reqBody);
  req.end();
} catch (err) {
  process.stderr.write('Error: ' + err.message);
  process.exit(1);
}
