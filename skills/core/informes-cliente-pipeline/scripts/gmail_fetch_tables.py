#!/usr/bin/env python3
"""Fetch all HTML tables of a Gmail message as pipe-separated rows.

Usage: gmail_fetch_tables.py /opt/data/secrets/<owner>-gmail.json "<exact subject>"
Verified 2026-09-14 against golden-gmail (KASSIUSS sales report tables).
"""
import json, sys, urllib.request, urllib.parse, time, re, html as H

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

enc = urllib.parse.urlencode({'q': 'subject:"' + subj + '"', 'maxResults': 2})
res = get(base + '/users/me/messages?' + enc)
mid = res['messages'][0]['id']
msg = get(base + '/users/me/messages/' + mid + '?format=full')

def find_html(p):
    if p.get('mimeType') == 'text/html' and p.get('body', {}).get('data'):
        return p['body']['data']
    for c in p.get('parts', []):
        r = find_html(c)
        if r: return r
    return ''

b64 = find_html(msg['payload'])
pad = len(b64) % 4
if pad: b64 += '=' * (4 - pad)
import base64
rawhtml = base64.urlsafe_b64decode(b64).decode('utf-8', 'replace')

tables = re.findall(r'<table[^>]*>(.*?)</table>', rawhtml, re.S | re.I)
print('NUM TABLES:', len(tables))
for ti, t in enumerate(tables):
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S | re.I)
    parsed = []
    for tr in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S | re.I)
        cells = [H.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in cells]
        parsed.append(cells)
    print(f'--- TABLE {ti+1} ({len(parsed)} rows) ---')
    for r in parsed:
        print(' | '.join(r))
