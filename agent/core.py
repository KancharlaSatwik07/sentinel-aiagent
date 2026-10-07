"""Validation and real pytest evidence; no shell commands or persistent projects."""
import difflib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

DEMOS = json.loads((Path(__file__).resolve().parent.parent / 'data/demos.json').read_text())
MAX_BYTES = 200_000


def test_file(path: str) -> bool:
    p = PurePosixPath(path)
    return p.name.startswith('test_') or p.name.endswith('_test.py') or 'tests' in p.parts or p.name == 'conftest.py'


def valid_path(path: str) -> None:
    if not isinstance(path, str) or not path or '\\' in path or '\x00' in path:
        raise ValueError('Invalid file path.')
    p = PurePosixPath(path)
    if p.is_absolute() or '..' in p.parts or str(p) != path or not path.endswith('.py') or any(x.startswith('.') for x in p.parts):
        raise ValueError('Only relative Python paths inside the project are allowed.')


def validate_files(files: dict) -> None:
    if not isinstance(files, dict) or not 1 <= len(files) <= 50:
        raise ValueError('Provide between 1 and 50 Python files.')
    size = 0
    for path, content in files.items():
        valid_path(path)
        if not isinstance(content, str):
            raise ValueError('File content must be text.')
        size += len(content.encode())
    if size > MAX_BYTES:
        raise ValueError('Project exceeds the 200 KB limit.')
    for path in files:
        if any(parent.as_posix() in files for parent in PurePosixPath(path).parents):
            raise ValueError('File paths conflict with a directory.')


def parse_proposal(text: str) -> dict:
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        text = '\n'.join(text.splitlines()[1:-1])
    try:
        value = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ValueError('The model returned malformed JSON. Retry the proposal.') from exc
    if not isinstance(value, dict) or not isinstance(value.get('explanation'), str) or not isinstance(value.get('edits'), list):
        raise ValueError('Expected an explanation and an edits array.')
    return value


def apply_edits(files: dict, edits: list) -> dict:
    validate_files(files)
    if not isinstance(edits, list) or not 1 <= len(edits) <= 50:
        raise ValueError('The proposal must contain 1–50 edits.')
    candidate = dict(files)
    seen = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {'file', 'content'}:
            raise ValueError('Each edit must have file and content fields.')
        path = edit['file']
        valid_path(path)
        if path in seen:
            raise ValueError('Duplicate edit path.')
        seen.add(path)
        if path in files and test_file(path):
            raise ValueError('Existing test files are protected.')
        if PurePosixPath(path).name == 'conftest.py':
            raise ValueError('Adding pytest configuration hooks is not allowed.')
        candidate[path] = edit['content']
    validate_files(candidate)
    return candidate


def ensure_execution_allowed(files: dict) -> None:
    # A subprocess is NOT a security boundary. Public hosting accepts only exact
    # reviewed demo snapshots; arbitrary code is an explicit local opt-in.
    for demo in DEMOS:
        if files == demo['files'] or files == {**demo['files'], **demo['fixed']}:
            return
    if os.getenv('ALLOW_TRUSTED_CODE') == '1' and not os.getenv('VERCEL'):
        return
    raise ValueError('Hosted demo safety: only unmodified built-in projects and reviewed fixes may execute. Run locally with ALLOW_TRUSTED_CODE=1 for trusted custom code.')


RUNNER = '''import json, pathlib, sys, pytest
class Evidence:
    def __init__(self):
        self.states = {}
        self.errors = []
    def pytest_runtest_logreport(self, report):
        old = self.states.get(report.nodeid)
        if report.failed:
            self.states[report.nodeid] = "failed"
        elif old != "failed" and report.skipped:
            self.states[report.nodeid] = "skipped"
        elif old not in ("failed", "skipped") and report.when == "call" and report.passed:
            self.states[report.nodeid] = "passed"
    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(report.nodeid)
e = Evidence()
code = pytest.main(["-q", "-p", "no:cacheprovider", "--tb=short", "."], plugins=[e])
pathlib.Path(sys.argv[1]).write_text(json.dumps({"states":e.states,"errors":e.errors,"exit_code":int(code)}))
'''


def run_tests(files: dict) -> dict:
    validate_files(files)
    ensure_execution_allowed(files)
    with tempfile.TemporaryDirectory(prefix='sentinel-', dir='/tmp') as tmp:
        root = Path(tmp) / 'project'
        root.mkdir()
        for path, content in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        report = Path(tmp) / 'evidence.json'
        env = {'PATH': os.defpath, 'HOME': tmp, 'TMPDIR': tmp, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'}
        # Output is bounded when returned. The reviewed demos produce tiny logs.
        with tempfile.TemporaryFile(dir='/tmp') as logs:
            try:
                result = subprocess.run([sys.executable, '-c', RUNNER, str(report)], cwd=root, env=env, stdout=logs, stderr=subprocess.STDOUT, timeout=8, check=False)
            except subprocess.TimeoutExpired as exc:
                raise ValueError('Test execution exceeded 8 seconds; no changes were kept.') from exc
            logs.seek(0)
            output = logs.read(24_000).decode(errors='replace')
        if not report.exists() or result.returncode != 0:
            raise ValueError('The test runner failed; no changes were kept.')
        evidence = json.loads(report.read_text())
        states = evidence['states']
        return {'passing': sorted(k for k,v in states.items() if v == 'passed'), 'failing': sorted(k for k,v in states.items() if v == 'failed'), 'skipped': sorted(k for k,v in states.items() if v == 'skipped'), 'errors': evidence['errors'], 'exit_code': evidence['exit_code'], 'output': output, 'valid': evidence['exit_code'] in (0, 1) and not evidence['errors'] and bool(states)}


def decide(baseline: dict, after: dict) -> dict:
    regressions = sorted(set(baseline['passing']) - set(after['passing']))
    missing = sorted((set(baseline['passing']) | set(baseline['failing'])) - (set(after['passing']) | set(after['failing'])))
    accepted = bool(baseline['valid'] and after['valid'] and not regressions and not missing and (len(after['failing']) < len(baseline['failing']) or not after['failing']))
    reason = 'Zero regressions. All baseline tests retained; failures reduced or all tests pass.' if accepted else 'Discarded: regression, missing/skipped test, invalid suite, or no reduction in failures.'
    return {'accepted': accepted, 'regressions': regressions, 'reason': reason}


def verify(files: dict, edits: list, baseline: dict | None = None) -> dict:
    candidate = apply_edits(files, edits)
    # Recompute instead of trusting browser-supplied baseline claims.
    before = run_tests(files)
    after = run_tests(candidate)
    diff = ''.join(''.join(difflib.unified_diff(files.get(path, '').splitlines(True), candidate[path].splitlines(True), fromfile='a/'+path, tofile='b/'+path)) for path in candidate if files.get(path) != candidate[path])
    return {**decide(before, after), 'baseline': before, 'after': after, 'diff': diff, 'files_changed': [p for p in candidate if candidate[p] != files.get(p)]}
