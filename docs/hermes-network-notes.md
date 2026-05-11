# Hermes Network Notes

## What we verified

- `GET /api/tags` on `http://192.168.100.41:11434` returns quickly.
- `GET /v1/models` on `http://192.168.100.41:11434` returns quickly.
- `POST /v1/chat/completions` on `http://192.168.100.41:11434` returns normally.
- Previously tested LAN hosts `192.168.50.141` and `192.168.100.34` were unhealthy.

## Likely conclusion

The configured LAN Ollama host `192.168.100.41:11434` is healthy enough to use as the primary endpoint.

That usually means one of these:

1. Some LAN hosts may expose Ollama discovery endpoints but still fail on generation.
2. The healthy host for this workspace is currently `192.168.100.41:11434`.
3. The smart launcher should remain the default entrypoint so endpoint health is checked at launch time.

## Smart launcher

Use this launcher instead of plain `hermes`:

```bash
cd "/Users/macminim4/Documents/New project/jyf0330-repos/ai-trading-assistant-main"
bash scripts/hermes-smart.sh
```

Behavior:

1. Probe LAN Ollama model list and chat POST health.
2. If LAN is healthy, use it.
3. If LAN chat health fails and local Ollama is healthy, fall back to local.
4. If only LAN model listing works, use LAN with a warning.

## Current local state

At the time of verification, local Ollama on `127.0.0.1:11434` was not running, so the healthy LAN host stayed primary.
