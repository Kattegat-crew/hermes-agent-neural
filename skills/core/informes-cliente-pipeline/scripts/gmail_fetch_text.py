#!/usr/bin/env python3
"""Fetch the plain-text body of a Gmail message by exact subject via OAuth secret.

Usage: gmail_fetch_text.py /opt/data/secrets/<owner>-gmail.json "<exact subject>"
Prints headers + body as text (prefers text/plain, falls back to stripped HTML).
Verified 2026-09-14 against golden-gmail (KASSIUSS informes).
"""
import json, sys, urllib.request, urllib.parse, time, re

secret_path = sys.argv[1]
subj = sys.argv[2]
d = json.load(open(secret_path))
body = urllib.parse.urlencode({'grant_type': 'refresh_token', 'refresh_token': d['refresh_token'],
                               'client_id': d['client_id'], 'client_secret': d['client_secret']}).encode()
req = urllib.request.Request('https://oauth2.googleapis.com/token', data=body,
                             headers={'Content-Type': 'application/x-www-form-urlencoded'})
with urllib.request.urlopen(req, timeout=30) as r:
    tok = json.load(r)['access_token']
base = 'https://gmail.googleapis.com/gmail/v1'

def get(url):
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
    for a in range(6):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(1.2); continue
            raise
    raise RuntimeError('rate limited')

enc = urllib.parse.urlencode({'q': 'subject:"' + subj + '"', 'maxResults': 3})
res = get(base + '/users/me/messages?' + enc)
if not res.get('messages'):
    print('NOT FOUND'); sys.exit(0)
mid = res['messages'][0]['id']
msg = get(base + '/users/me/messages/' + mid + '?format=full')

def decode_part(part):
    if part.get('body', {}).get('data'):
        data = part['body']['data']
        pad = len(data) % 4
        if pad: data += '=' * (4 - pad)
        import base64
        try:
            return base64.urlsafe_b64decode(data).decode('utf-8', 'replace')
        except Exception:
            return ''
    return ''

text = ''
def walk(p):
    global text
    if p.get('mimeType') == 'text/plain' and p.get('body', {}).get('data'):
        text += decode_part(p) + '\n'
    if p.get('mimeType') == 'text/html' and p.get('body', {}).get('data'):
        html = decode_part(p)
        html = re.sub(r'<br[^>]*>', '\n', html)
        html = re.sub(r'</p>|</tr>|</div>', '\n', html)
        html = re.sub(r'<[^>]+>', ' ', html)
        import html as H
        txt = H.unescape(html)
        txt = re.sub(r'\n\s*\n+', '\n', txt)
        if not text.strip():
            text = txt
    for c in p.get('parts', []):
        walk(c)

walk(msg['payload'])
hdrs = {h['name'].lower(): h['value'] for h in msg['payload']['headers']}
print('SUBJECT:', hdrs.get('subject'))
print('FROM:', hdrs.get('from'))
print('DATE:', hdrs.get('date'))
print('=' * 40)
print(text.strip()[:4000])
