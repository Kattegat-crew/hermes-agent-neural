# GitHub commit-attribution via REST API (no gh CLI, unauthenticated)

Context: on this host `gh` is NOT installed and there is no GitHub token in env, so attribution goes through `https://api.github.com`. Unauthenticated rate limit is 60 req/h — budget it.

## Pitfall: `?since=` can 500 and return an EMPTY body

The commits endpoint with `since=<iso>&per_page=100` returned `HTTP 500` with 0 bytes (observed both with `--data-urlencode` and joined plainly); a retry loop on the *same* query kept failing 5x. What worked:

1. Drop the `since` parameter entirely: fetch the default listing (`per_page=50`) — succeeded on the first try with identical headers/rate-limit budget.
2. Filter the 48h window **client-side** in Python against `commit.author.date >= cutoff` (compute cutoff with `datetime.now(timezone.utc) - timedelta(hours=48)`).
3. Sanity check: newest commit date in the payload should be recent; `len(recent)` reasonable vs. repo activity.

```bash
curl -sS -G --max-time 40 -D headers.txt \
  "https://api.github.com/repos/<org>/<repo>/commits" \
  --data-urlencode "per_page=50" -o commits.json
# check HTTP status + x-ratelimit-remaining in headers.txt before parsing
```

## Verifying identity vs. display name

- `GET /users/<login>` → profile fields (name/email/bio often null; weak signal alone).
- Stronger: the repo's contributor email map — for hermes-agent, `/opt/hermes/contributors/emails/*` files map email→login; grep for the person's known email(s). Near-miss usernames (e.g. a nickname resembling the target's name) must be cleared by an email match before attributing commits to them.

## Fork/coordination checks

- `GET /search/repositories?q=<repo>+in:name+fork:true&sort=updated` to spot the user's fork when the local clone is root-owned and unreadable — but forks listed there are not necessarily the user's; don't claim without checking `owner.login`.
