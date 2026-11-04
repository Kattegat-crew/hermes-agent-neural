# Hermes Profile Repository Structure

```
github.com/NeuralCrewLabs/hermes-profiles/
├── README.md
├── .github/workflows/
│   └── deploy.yml
├── profiles/
│   ├── default/           # Ragnar orchestrator
│   │   ├── config.yaml
│   │   ├── SOUL.md
│   │   ├── AGENTS.md
│   │   ├── MEMORY.md
│   │   ├── skills.list
│   │   └── cron/
│   ├── golden-game/       # Client profile (same structure)
│   ├── lucky-club/
│   ├── bendabal/
│   └── guaya-racing/
├── shared/
│   ├── base-skills/
│   └── templates/
└── scripts/
    ├── deploy-profile.sh
    └── validate-profile.sh
```

## CI/CD Pipeline

```yaml
name: Deploy Hermes Profile
on:
  push:
    branches: [main]
    paths: ["profiles/**", "shared/**"]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate profiles
        run: |
          for p in profiles/*/; do
            n=$(basename "$p")
            [ -f "$p/config.yaml" ] || { echo "Missing config in $n"; exit 1; }
            [ -f "$p/SOUL.md" ] || { echo "Missing SOUL in $n"; exit 1; }
          done
  deploy:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Coolify
        run: |
          curl -X POST "$COOLIFY_URL/api/v1/deploy" \
            -H "Authorization: Bearer $COOLIFY_TOKEN" \
            -H "Content-Type: application/json"
```

## Validation Script

```bash
#!/bin/bash
# validate-profile.sh — Validate a profile before deploy
PROFILE=$1
[ -z "$PROFILE" ] && { echo "Usage: $0 <profile-name>"; exit 1; }

DIR="profiles/$PROFILE"
[ -d "$DIR" ] || { echo "Profile $PROFILE not found"; exit 1; }
[ -f "$DIR/config.yaml" ] || { echo "Missing config.yaml"; exit 1; }
[ -f "$DIR/SOUL.md" ] || { echo "Missing SOUL.md"; exit 1; }

echo "✅ $PROFILE: valid"
```