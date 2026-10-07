"""Local development API. Intentionally binds to loopback only."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.http import Handler
print('Sentinel API listening on http://127.0.0.1:8000', flush=True)
ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
