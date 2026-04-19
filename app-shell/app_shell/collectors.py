from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import ROOT, SNAPSHOT_PATHS, VENDOR_NAMES, VENDOR_PATHS


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_text(path: Path, limit: int = 6000) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding='utf-8', errors='ignore')[:limit]
    except Exception:
        return None


def run_git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ['git', '-C', str(repo), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def repo_metadata(repo: Path) -> dict[str, Any]:
    files = list(repo.rglob('*')) if repo.exists() else []
    readme = next((p for p in [repo / 'README.md', repo / 'README.MD'] if p.exists()), None)
    return {
        'exists': repo.exists(),
        'path': str(repo),
        'git_head': run_git(repo, 'rev-parse', '--short', 'HEAD') if repo.exists() else None,
        'git_branch': run_git(repo, 'rev-parse', '--abbrev-ref', 'HEAD') if repo.exists() else None,
        'file_count': sum(1 for p in files if p.is_file()),
        'readme_path': str(readme) if readme else None,
        'readme_excerpt': safe_text(readme, 2500) if readme else None,
    }


def write_snapshot(vendor: str, payload: dict[str, Any], markdown: str) -> None:
    target_dir = SNAPSHOT_PATHS[vendor]
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / 'latest.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    (target_dir / 'latest.md').write_text(markdown, encoding='utf-8')


def discover_ollama() -> dict[str, Any]:
    candidates: list[str] = []
    env_host = os.getenv('OLLAMA_HOST')
    if env_host:
        candidates.append(env_host.rstrip('/'))
    candidates.extend(['http://127.0.0.1:11434'])
    try:
        route = subprocess.run(
            ['bash', '-lc', "ip route | awk '/default/ {print $3}' | head -n 1"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        gateway = route.stdout.strip()
        if gateway:
            candidates.append(f'http://{gateway}:11434')
    except Exception:
        gateway = None

    checked = []
    for host in candidates:
        if host in checked:
            continue
        checked.append(host)
        try:
            with httpx.Client(timeout=3.0) as client:
                response = client.get(f'{host}/api/tags')
                data = response.json()
                models = data.get('models', [])
                return {
                    'reachable': True,
                    'host': host,
                    'models': models,
                    'model_names': [item.get('name') for item in models],
                }
        except Exception:
            continue
    return {
        'reachable': False,
        'host': checked[0] if checked else None,
        'models': [],
        'model_names': [],
    }


def collect_journedge() -> dict[str, Any]:
    repo = VENDOR_PATHS['journedge']
    meta = repo_metadata(repo)
    db_candidates = sorted(repo.glob('prisma/**/*.db'))
    db_path = db_candidates[0] if db_candidates else None
    stats: dict[str, Any] = {
        'db_found': bool(db_path),
        'db_path': str(db_path) if db_path else None,
        'trade_count': None,
        'account_count': None,
        'total_pnl': None,
        'win_count': None,
        'loss_count': None,
        'recent_trades': [],
    }
    if db_path:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM Trade')
            stats['trade_count'] = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM Account')
            stats['account_count'] = cur.fetchone()[0]
            cur.execute('SELECT COALESCE(SUM(pnl), 0) FROM Trade')
            stats['total_pnl'] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM Trade WHERE status = 'WIN'")
            stats['win_count'] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM Trade WHERE status = 'LOSS'")
            stats['loss_count'] = cur.fetchone()[0]
            cur.execute(
                '''
                SELECT id, date, symbol, type, direction, quantity, entryPrice, exitPrice, pnl, status, createdAt
                FROM Trade
                ORDER BY datetime(createdAt) DESC
                LIMIT 20
                '''
            )
            stats['recent_trades'] = [dict(row) for row in cur.fetchall()]
            conn.close()
        except Exception as exc:
            stats['error'] = str(exc)
    payload = {
        'vendor': 'journedge',
        'generated_at': now_iso(),
        'repo': meta,
        'stats': stats,
        'status': 'ready' if stats['db_found'] else 'partial',
        'source_files': [str(p) for p in db_candidates[:5]],
    }
    md = (
        '# Journedge Snapshot\n\n'
        f"- Generated: {payload['generated_at']}\n"
        f"- Repo: {meta['path']}\n"
        f"- Git: {meta['git_head']}\n"
        f"- DB found: {stats['db_found']}\n"
        f"- Trade count: {stats['trade_count']}\n"
        f"- Account count: {stats['account_count']}\n"
        f"- Total PnL: {stats['total_pnl']}\n"
    )
    write_snapshot('journedge', payload, md)
    return payload


def collect_tradingagents() -> dict[str, Any]:
    repo = VENDOR_PATHS['tradingagents']
    meta = repo_metadata(repo)
    results_dir = Path.home() / '.tradingagents' / 'logs'
    cache_dir = Path.home() / '.tradingagents' / 'cache'
    providers = [
        'OPENAI_API_KEY',
        'GOOGLE_API_KEY',
        'ANTHROPIC_API_KEY',
        'XAI_API_KEY',
        'DEEPSEEK_API_KEY',
        'DASHSCOPE_API_KEY',
        'ZHIPU_API_KEY',
        'OPENROUTER_API_KEY',
        'ALPHA_VANTAGE_API_KEY',
    ]
    env_status = {key: bool(os.getenv(key)) for key in providers}
    log_files = (
        sorted([p for p in results_dir.rglob('*') if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
        if results_dir.exists()
        else []
    )
    ollama = discover_ollama()
    status = 'blocked_no_key'
    if ollama['reachable'] and ollama['model_names']:
        status = 'ready_local_model'
    elif any(env_status.values()):
        status = 'ready_remote_model'
    payload = {
        'vendor': 'tradingagents',
        'generated_at': now_iso(),
        'repo': meta,
        'status': status,
        'env_status': env_status,
        'results_dir': str(results_dir),
        'cache_dir': str(cache_dir),
        'recent_result_files': [str(p) for p in log_files[:10]],
        'default_config_excerpt': safe_text(repo / 'tradingagents' / 'default_config.py', 2500),
        'ollama': ollama,
    }
    md = (
        '# TradingAgents Snapshot\n\n'
        f"- Generated: {payload['generated_at']}\n"
        f"- Repo: {meta['path']}\n"
        f"- Git: {meta['git_head']}\n"
        f"- Status: {payload['status']}\n"
        f"- Results dir: {payload['results_dir']}\n"
        f"- Cache dir: {payload['cache_dir']}\n"
        f"- Ollama reachable: {ollama['reachable']}\n"
        f"- Ollama host: {ollama['host']}\n"
        f"- Ollama models: {', '.join(ollama['model_names']) if ollama['model_names'] else 'none'}\n\n"
        '## API keys detected\n' + '\n'.join(f"- {k}: {'yes' if v else 'no'}" for k, v in env_status.items())
    )
    write_snapshot('tradingagents', payload, md)
    return payload


def try_get(url: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            return {
                'ok': True,
                'status_code': response.status_code,
                'body': response.text[:2000],
            }
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def collect_open_paper() -> dict[str, Any]:
    repo = VENDOR_PATHS['open-paper-trading-mcp']
    meta = repo_metadata(repo)
    health = try_get('http://127.0.0.1:2080/health')
    trading_health = try_get('http://127.0.0.1:2080/api/v1/trading/health')
    mcp_root = try_get('http://127.0.0.1:2081/')
    portfolio = try_get('http://127.0.0.1:2080/api/v1/trading/portfolio')
    payload = {
        'vendor': 'open-paper-trading-mcp',
        'generated_at': now_iso(),
        'repo': meta,
        'status': 'ready' if health.get('ok') else 'partial',
        'fastapi_health': health,
        'trading_health': trading_health,
        'mcp_root': mcp_root,
        'portfolio': portfolio,
        'docker_compose_excerpt': safe_text(repo / 'docker-compose.yml', 2200),
    }
    md = (
        '# Open Paper Trading MCP Snapshot\n\n'
        f"- Generated: {payload['generated_at']}\n"
        f"- Repo: {meta['path']}\n"
        f"- Git: {meta['git_head']}\n"
        f"- FastAPI health ok: {health.get('ok')}\n"
        f"- Trading health ok: {trading_health.get('ok')}\n"
        f"- MCP root ok: {mcp_root.get('ok')}\n"
    )
    write_snapshot('open-paper-trading-mcp', payload, md)
    return payload


def collect_vectorbt() -> dict[str, Any]:
    repo = VENDOR_PATHS['vectorbt-lab']
    meta = repo_metadata(repo)
    examples = sorted((repo / 'examples').glob('*')) if (repo / 'examples').exists() else []
    tests = sorted((repo / 'tests').glob('*.py')) if (repo / 'tests').exists() else []
    payload = {
        'vendor': 'vectorbt-lab',
        'generated_at': now_iso(),
        'repo': meta,
        'status': 'ready' if repo.exists() else 'missing',
        'example_files': [str(p) for p in examples[:20]],
        'test_files': [str(p) for p in tests[:20]],
        'readme_excerpt': safe_text(repo / 'README.md', 2500),
    }
    md = (
        '# vectorbt Snapshot\n\n'
        f"- Generated: {payload['generated_at']}\n"
        f"- Repo: {meta['path']}\n"
        f"- Git: {meta['git_head']}\n"
        f"- Example files: {len(payload['example_files'])}\n"
        f"- Test files: {len(payload['test_files'])}\n"
    )
    write_snapshot('vectorbt-lab', payload, md)
    return payload


COLLECTORS = {
    'journedge': collect_journedge,
    'tradingagents': collect_tradingagents,
    'open-paper-trading-mcp': collect_open_paper,
    'vectorbt-lab': collect_vectorbt,
}


def collect_all() -> dict[str, Any]:
    results = {}
    for vendor in VENDOR_NAMES:
        try:
            results[vendor] = COLLECTORS[vendor]()
        except Exception as exc:
            payload = {
                'vendor': vendor,
                'generated_at': now_iso(),
                'status': 'error',
                'error': str(exc),
                'repo': repo_metadata(VENDOR_PATHS[vendor]),
            }
            write_snapshot(vendor, payload, f'# {vendor}\n\n- Error: {exc}\n')
            results[vendor] = payload
    index = {
        'generated_at': now_iso(),
        'vendors': results,
        'root': str(ROOT),
    }
    root_index = ROOT / 'data' / 'snapshots' / 'index.json'
    root_index.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    return index


def main() -> None:
    result = collect_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
