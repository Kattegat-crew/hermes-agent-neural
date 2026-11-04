---
name: provider-manager
description: "Use when adding, switching or testing an LLM provider."
tags: [providers, config, modelos, hermes, llm, api-key]
---

# Provider Manager Skill

Use this skill whenever the user asks to configure, add, update, or test an AI provider or LLM model.

## Quick CLI Usage

You can use the built-in helper script `/opt/data/scripts/manage_provider.py`:

### 1. List configured providers:
```bash
python3 /opt/data/scripts/manage_provider.py list
```

### 2. Add a new OpenAI-compatible provider:
```bash
python3 /opt/data/scripts/manage_provider.py add \
  --name "ProviderName" \
  --base-url "https://api.example.com/v1" \
  --api-key "sk-..." \
  --model "model-name" \
  --context-length 1048576 \
  --display-name "Model Display Name"
```

### 3. Test provider connectivity:
```bash
python3 /opt/data/scripts/manage_provider.py test --name "ProviderName"
```

### 4. Switch active default model:
```bash
python3 /opt/data/scripts/manage_provider.py set-default --name "ProviderName" --model "model-name"
```

### 5. Remove a provider (borra de `providers` y `custom_providers`):
```bash
python3 /opt/data/scripts/manage_provider.py remove --name "ProviderName"
```

> **Nota:** `save_config` genera backup automático (`config.yaml.bak-<timestamp>`) antes de cada escritura porque `yaml.dump` pierde comentarios. Si algo sale mal, restaurar desde el backup.

## Structure in `config.yaml`
When modifying `config.yaml` manually:
1. `providers.<Name>` contains `api_key`, `base_url`, and `models.<model_id>.context_length`.
2. `custom_providers` contains matching entry for legacy client support.
3. `model` contains the currently active `default`, `provider: custom`, `api_key`, and `base_url`.
