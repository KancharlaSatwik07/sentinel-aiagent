"""Local development API. Binds to loopback only; never expose this server."""
import os
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PYTHON = ROOT / '.venv' / 'bin' / 'python'
if EXPECTED_PYTHON.is_file() and Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
    raise SystemExit(f'Use the project interpreter: {EXPECTED_PYTHON}')
sys.path.insert(0, str(ROOT))


def load_local_env():
    path = ROOT / '.env'
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key.replace('_', '').isalnum():
            os.environ.setdefault(key, value)


load_local_env()
from agent.http import Handler  # noqa: E402

print('Sentinel API listening on http://127.0.0.1:8000', flush=True)
ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
