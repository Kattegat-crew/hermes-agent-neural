#!/bin/bash
# Lanzador: extracción del grafo del Brain v2 (dir hermes-owned, cache funcional)
export OPENAI_BASE_URL="https://api.nan.builders/v1"
export OPENAI_MODEL="deepseek-v4-flash"
# La key se inyecta desde el entorno del llamador

cd /opt/hermes-agent-data
/opt/hermes-agent-data/.venv-graphify/bin/graphify extract /opt/hermes-agent-data/brain \
  --backend openai \
  --out /opt/hermes-agent-data/brain/graphify-out-v2 \
  --max-concurrency 2 \
  --api-timeout 120 > /opt/hermes-agent-data/brain/graphify_update.log 2>&1

echo "EXIT: $?" >> /opt/hermes-agent-data/brain/graphify_update.log
