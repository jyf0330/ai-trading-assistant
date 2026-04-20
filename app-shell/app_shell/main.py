from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .collectors import collect_all
from .config import ROOT, SNAPSHOT_PATHS, VENDOR_NAMES
from .journedge_export import load_journedge_export
from .local_ops import (
    build_behavior_profile,
    list_analysis_runs,
    load_local_paper_account,
    local_paper_summary,
    run_ma_strategy,
    run_tradingagents_analysis,
    run_a_share_analysis,
)

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


def load_exported_journedge() -> dict[str, Any]:
    export_path = ROOT / 'data' / 'exports' / 'journedge' / 'latest.json'
    exported = load_json(export_path)
    if exported:
        return exported
    return load_journedge_export()


def build_records_context() -> dict[str, Any]:
    snapshot = load_snapshot('journedge') or {}
    exported = load_exported_journedge()
    summary = exported.get('summary', {})
    return {
        'snapshot': snapshot,
        'exported': exported,
        'stats': {
            'trade_count': summary.get('trade_count', 0),
            'account_count': summary.get('account_count', 0),
            'total_pnl': summary.get('total_pnl', 0),
            'win_count': summary.get('win_count', 0),
            'loss_count': summary.get('loss_count', 0),
        },
        'recent_trades': exported.get('recent_trades', [])[:20],
        'accounts': exported.get('accounts', []),
        'tag_frequency': summary.get('tag_frequency', [])[:10],
    }


def build_analysis_context() -> dict[str, Any]:
    snapshot = load_snapshot('tradingagents') or {}
    vectorbt_snapshot = load_snapshot('vectorbt-lab') or {}
    env_status = snapshot.get('env_status', {})
    enabled_keys = [key for key, enabled in env_status.items() if enabled]
    ollama = snapshot.get('ollama', {})
    return {
        'snapshot': snapshot,
        'enabled_keys': enabled_keys,
        'recent_result_files': compact_paths(snapshot.get('recent_result_files', [])),
        'vectorbt_snapshot': vectorbt_snapshot,
        'example_files': compact_paths(vectorbt_snapshot.get('example_files', [])),
        'ollama': ollama,
        'ollama_models': ollama.get('model_names') or [item.get('name') for item in ollama.get('models', []) if item.get('name')],
        'ollama_host': ollama.get('host'),
        'ollama_reachable': ollama.get('reachable', False),
        'analysis_runs': list_analysis_runs(),
    }


def build_paper_context() -> dict[str, Any]:
    snapshot = load_snapshot('open-paper-trading-mcp') or {}
    accounts_payload = parse_body_payload(snapshot.get('accounts'))
    orders_payload = parse_body_payload(snapshot.get('orders'))
    local_account = load_local_paper_account()
    return {
        'snapshot': snapshot,
        'fastapi_payload': parse_body_payload(snapshot.get('fastapi_health')),
        'trading_payload': parse_body_payload(snapshot.get('trading_health')),
        'portfolio_payload': parse_body_payload(snapshot.get('portfolio')),
        'accounts_payload': accounts_payload,
        'orders_payload': orders_payload,
        'local_paper': local_paper_summary(local_account),
    }


def build_behavior_context() -> dict[str, Any]:
    profile = build_behavior_profile()
    return {
        'profile': profile,
    }


@app.get('/', response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    snapshots = load_snapshots()
    local_paper = local_paper_summary(load_local_paper_account())
    analysis_runs = list_analysis_runs()
    behavior = build_behavior_profile()
    return templates.TemplateResponse(
        request,
        'home.html',
        {
            'snapshots': snapshots,
            'vendors': VENDOR_NAMES,
            'root': str(ROOT),
            'local_paper': local_paper,
            'analysis_runs_count': len(analysis_runs),
            'behavior_event_count': behavior['behavior_event_count'],
        },
    )


@app.get('/records', response_class=HTMLResponse)
def records(request: Request) -> HTMLResponse:
    context = build_records_context()
    return templates.TemplateResponse(request, 'records.html', context)


@app.get('/behavior', response_class=HTMLResponse)
def behavior(request: Request) -> HTMLResponse:
    context = build_behavior_context()
    return templates.TemplateResponse(request, 'behavior.html', context)


@app.get('/analysis', response_class=HTMLResponse)
def analysis(request: Request) -> HTMLResponse:
    context = build_analysis_context()
    return templates.TemplateResponse(request, 'analysis.html', context)


@app.post('/analysis/run', response_class=HTMLResponse)
def analysis_run(
    request: Request,
    symbol: str = Form(...),
    trade_date: str = Form(...),
) -> HTMLResponse:
    context = build_analysis_context()
    try:
        from .local_ops import is_a_share_symbol, normalize_symbol
        if is_a_share_symbol(symbol):
            context['run_result'] = run_a_share_analysis(normalize_symbol(symbol), trade_date)
        else:
            context['run_result'] = run_tradingagents_analysis(symbol, trade_date)
    except Exception as exc:
        context['run_result'] = {
            'symbol': symbol.upper(),
            'trade_date': trade_date,
            'summary': str(exc),
            'error': True,
            'model': 'qwen3.6:35b-a3b-q4_K_M',
            'result_path': None,
        }
    context['analysis_runs'] = list_analysis_runs()
    return templates.TemplateResponse(request, 'analysis.html', context)


@app.get('/paper', response_class=HTMLResponse)
def paper(request: Request) -> HTMLResponse:
    context = build_paper_context()
    return templates.TemplateResponse(request, 'paper.html', context)


@app.post('/paper/strategy-run', response_class=HTMLResponse)
def paper_strategy_run(
    request: Request,
    symbol: str = Form(...),
    allocation: float = Form(1000.0),
) -> HTMLResponse:
    context = build_paper_context()
    try:
        context['strategy_result'] = run_ma_strategy(symbol, allocation)
    except Exception as exc:
        context['strategy_result'] = {
            'symbol': symbol.upper(),
            'action': 'error',
            'signal': 'error',
            'message': str(exc),
        }
    context['local_paper'] = local_paper_summary(load_local_paper_account())
    return templates.TemplateResponse(request, 'paper.html', context)


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
