import json
from http.server import BaseHTTPRequestHandler
from agent.core import run_tests, verify
from agent.github import import_github
from agent.model import check_openrouter, propose, status


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log submitted source, repository data, or provider information.

    def reply(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split('?')[0] == '/api/status':
            return self.reply(200, status())
        self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1_500_000:
                raise ValueError('Request body is missing or too large.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Expected a JSON object.')
            path = self.path.split('?')[0]
            if path == '/api/baseline':
                result = run_tests(payload.get('files'))
            elif path == '/api/propose':
                result = propose(payload)
            elif path == '/api/verify':
                result = verify(payload.get('files'), payload.get('edits'), payload.get('baseline'))
            elif path == '/api/openrouter-check':
                result = check_openrouter()
            elif path == '/api/import-github':
                result = import_github(payload.get('url'))
            else:
                return self.reply(404, {'error': 'Not found'})
            self.reply(200, result)
        except (ValueError, TypeError, KeyError) as exc:
            self.reply(400, {'error': str(exc)})
        except Exception:
            self.reply(500, {'error': 'The request could not finish. No changes were kept.'})
