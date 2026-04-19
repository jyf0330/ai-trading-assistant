# AI Trading Assistant Vendor Run Status

Project root:

- `/home/ywh/projects/ai-trading-assistant`

Current vendor status:

- `journedge`: running locally on `http://localhost:3000`
- `open-paper-trading-mcp` FastAPI: running locally on `http://localhost:2080`
- `open-paper-trading-mcp` MCP: running locally on `http://localhost:2081`
- `tradingagents`: installed and importable, but blocked on missing LLM provider API key

Notes:

- `journedge` needed `npm install --package-lock=false` because the vendor lockfile is not fully in sync with `package.json`.
- `open-paper-trading-mcp` vendor Docker build currently fails because its `pyproject.toml` places `dependencies` under `project.urls`.
- To avoid editing vendor source, the local startup script installs dependencies directly from the declared list, starts only the `db` container, and runs FastAPI/MCP from a local venv.
- `open-paper-trading-mcp` MCP also needed `pydantic<2.12` in the local venv to avoid a FastMCP startup crash.
- `tradingagents` can be installed cleanly, but a real analysis run still requires a supported LLM API key. This is a hard dependency of the upstream project.

Useful scripts:

- `/home/ywh/projects/ai-trading-assistant/scripts/start-journedge.sh`
- `/home/ywh/projects/ai-trading-assistant/scripts/start-open-paper-trading.sh`
- `/home/ywh/projects/ai-trading-assistant/scripts/setup-tradingagents.sh`