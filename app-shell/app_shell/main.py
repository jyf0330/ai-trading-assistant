from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .collectors import collect_all
from .config import ROOT, SNAPSHOT_PATHS, VENDOR_NAMES

app = FastAPI(title='AI Trading Assistant Shell', version='0.1.0')

templates = Jinja2Templates(directory=str(ROOT / 'app-shell' / 'app_shell' / 'templates'))
app.mount('/static', StaticFiles(directory=str(ROOT / 'app-shell' / 'app_shell' / 'static')), name='static')


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def load_snapshots() -> dict[str, Any]:
    return {vendor: load_json(SNAPSHOT_PATHS[vendor] / 'latest.json') for vendor in VENDOR_NAMES}


def load_snapshot(vendor: str) -> dict[str, Any] | None:
    return load_json(SNAPSHOT_PATHS[vendor] / 'latest.json')


def parse_body_payload(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item or not item.get('body'):
        return None
    try:
        return json.loads(item['body'])
    except Exception:
        return None


def compact_paths(paths: list[str], limit: int = 8) -> list[str]:
    return paths[:limit] if paths else []


@app.get('/', response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    snapshots = load_snapshots()
    return templates.TemplateResponse(
        request,
        'home.html',
        {
            'snapshots': snapshots,
            'vendors': VENDOR_NAMES,
            'root': str(ROOT),
        },
    )


@app.get('/records', response_class=HTMLResponse)
def records(request: Request) -> HTMLResponse:
    snapshot = load_snapshot('journedge') or {}
    stats = snapshot.get('stats', {})
    return templates.TemplateResponse(
        request,
        'records.html',
        {
            'snapshot': snapshot,
            'stats': stats,
            'recent_trades': stats.get('recent_trades', []),
        },
    )


@app.get('/analysis', response_class=HTMLResponse)
def analysis(request: Request) -> HTMLResponse:
    snapshot = load_snapshot('tradingagents') or {}
    vectorbt_snapshot = load_snapshot('vectorbt-lab') or {}
    env_status = snapshot.get('env_status', {})
    enabled_keys = [key for key, enabled in env_status.items() if enabled]
    ollama = snapshot.get('ollama', {})
    return templates.TemplateResponse(
        request,
        'analysis.html',
        {
            'snapshot': snapshot,
            'enabled_keys': enabled_keys,
            'recent_result_files': compact_paths(snapshot.get('recent_result_files', [])),
            'vectorbt_snapshot': vectorbt_snapshot,
            'example_files': compact_paths(vectorbt_snapshot.get('example_files', [])),
            'ollama': ollama,
            'ollama_models': ollama.get('model_names') or [item.get('name') for item in ollama.get('models', []) if item.get('name')],
            'ollama_host': ollama.get('host'),
            'ollama_reachable': ollama.get('reachable', False),
        },
    )


@app.get('/paper', response_class=HTMLResponse)
def paper(request: Request) -> HTMLResponse:
    snapshot = load_snapshot('open-paper-trading-mcp') or {}
    return templates.TemplateResponse(
        request,
        'paper.html',
        {
            'snapshot': snapshot,
            'fastapi_payload': parse_body_payload(snapshot.get('fastapi_health')),
            'trading_payload': parse_body_payload(snapshot.get('trading_health')),
            'portfolio_payload': parse_body_payload(snapshot.get('portfolio')),
        },
    )


@app.get('/vendors/{vendor}', response_class=HTMLResponse)
def vendor_detail(vendor: str, request: Request) -> HTMLResponse:
    if vendor not in VENDOR_NAMES:
        return templates.TemplateResponse(
            request,
            'vendor.html',
            {'vendor': vendor, 'snapshot': None, 'error': 'Vendor not found'},
            status_code=404,
        )
    snapshot = load_json(SNAPSHOT_PATHS[vendor] / 'latest.json')
    markdown = (
        (SNAPSHOT_PATHS[vendor] / 'latest.md').read_text(encoding='utf-8')
        if (SNAPSHOT_PATHS[vendor] / 'latest.md').exists()
        else None
    )
    return templates.TemplateResponse(
        request,
        'vendor.html',
        {
            'vendor': vendor,
            'snapshot': snapshot,
            'markdown': markdown,
            'error': None,
        },
    )


@app.get('/refresh')
def refresh() -> RedirectResponse:
    collect_all()
    return RedirectResponse(url='/', status_code=303)


@app.get('/api/snapshots')
def snapshots_api() -> dict[str, Any]:
    return load_snapshots()


def main() -> None:
    import uvicorn

    uvicorn.run('app_shell.main:app', host='0.0.0.0', port=8090, reload=False)


if __name__ == '__main__':
    main()

