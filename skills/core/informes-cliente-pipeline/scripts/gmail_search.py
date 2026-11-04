#!/usr/bin/env python3
"""Search a Gmail mailbox via a per-owner OAuth secret (no SDK).

Usage: gmail_search.py /opt/data/secrets/<owner>-gmail.json "<query>" [maxResults]
Prints: 'Date | From | Subject' per message plus the estimated total.
Verified 2026-09-14 against golden-gmail (KASSIUSS informes).
"""
import json, sys, time, urllib.request, urllib.parse, urllib.error

secret_path, query = sys.argv[1], sys.argv[2]
max_results = sys.argv[3] if len(sys.argv) > 3 else '20'
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
    for _ in range(6):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(1.2); continue
            raise
    raise RuntimeError('rate limited')

enc = urllib.parse.urlencode({'q': query, 'maxResults': max_results})
res = get(base + '/users/me/messages?' + enc)
msgs = res.get('messages', [])
print(f'QUERY: {query}')
print(f'TOTAL (estimate): {res.get("resultSizeEstimate", len(msgs))}')
for m in msgs:
    msg = get(base + '/users/me/messages/' + m['id'] + '?format=metadata'
              '&metadataHeaders=Date&metadataHeaders=From&metadataHeaders=Subject')
    h = {x['name']: x['value'] for x in msg['payload']['headers']}
    print(f"- {h.get('Date', '')} | {h.get('From', '')} | {h.get('Subject', '')}")
