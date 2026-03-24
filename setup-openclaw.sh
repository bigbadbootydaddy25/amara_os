#!/usr/bin/env bash
set -euo pipefail

mkdir -p ~/.openclaw
cat > ~/.openclaw/openclaw.json <<'EOF'
{
  "meta": {
    "lastTouchedVersion": "2026.3.2",
    "lastTouchedAt": "2026-03-24T21:15:00.000Z"
  },
  "env": {
    "OPENAI_BASE_URL": "http://127.0.0.1:11434/v1",
    "OPENAI_API_KEY": "ollama"
  },
  "auth": {
    "profiles": {
      "ollama": {
        "provider": "openai",
        "mode": "api_key"
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/llama3.1:8b"
      },
      "compaction": {
        "mode": "safeguard"
      }
    }
  },
  "commands": {
    "native": "auto",
    "nativeSkills": "auto",
    "restart": false,
    "ownerDisplay": "raw"
  },
  "channels": {
    "telegram": {
      "enabled": false
    }
  },
  "gateway": {
    "mode": "local"
  }
}
EOF

openclaw gateway install
openclaw gateway start
sleep 3
openclaw gateway status
