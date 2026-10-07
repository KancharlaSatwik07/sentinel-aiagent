"""Bounded project validation and pytest evidence collection."""
import difflib
import ast
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

MAX_BYTES = 200_000
MAX_FILES = 50


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
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError(f'Provide between 1 and {MAX_FILES} Python files.')
    size = 0
    for path, content in files.items():
        valid_path(path)
        if not isinstance(content, str):
            raise ValueError('File content must be text.')
        size += len(content.encode('utf-8'))
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
    if not isinstance(edits, list) or not 1 <= len(edits) <= MAX_FILES:
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
        if not isinstance(edit['content'], str):
            raise ValueError('File content must be text.')
        candidate[path] = edit['content']
    validate_files(candidate)
    return candidate


def ensure_execution_allowed(files: dict) -> None:
    """Never execute user source on hosted functions; local execution is opt-in."""
    validate_files(files)
    if os.getenv('VERCEL') or os.getenv('ALLOW_TRUSTED_CODE') != '1':
        raise ValueError('Code execution is disabled. Run the local server with ALLOW_TRUSTED_CODE=1 only for code you trust; hosted execution requires an isolated sandbox.')


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
    test_files = sorted(path for path in files if test_file(path))
    if not test_files:
        passing = []
        failing = []
        diagnostics = ['No pytest files found. Running Python syntax checks only; describe the expected behavior and the AI will add regression tests with its proposal.']
        for path, content in sorted(files.items()):
            try:
                ast.parse(content, filename=path)
                passing.append(f'syntax::{path}')
            except SyntaxError as exc:
                failing.append(f'syntax::{path}')
                diagnostics.append(f'{path}:{exc.lineno or 1}:{exc.offset or 1}: SyntaxError: {exc.msg}')
        return {
            'passing': passing,
            'failing': failing,
            'skipped': [],
            'errors': [],
            'test_files': [],
            'mode': 'static',
            'exit_code': 1 if failing else 0,
            'output': '\n'.join(diagnostics),
            'valid': True,
        }
    ensure_execution_allowed(files)
    with tempfile.TemporaryDirectory(prefix='sentinel-', dir='/tmp') as tmp:
        root = Path(tmp) / 'project'
        root.mkdir()
        for path, content in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        report = Path(tmp) / 'evidence.json'
        env = {'PATH': os.defpath, 'HOME': tmp, 'TMPDIR': tmp, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'}
        with tempfile.TemporaryFile(dir='/tmp') as logs:
            try:
                result = subprocess.run([sys.executable, '-c', RUNNER, str(report)], cwd=root, env=env, stdout=logs, stderr=subprocess.STDOUT, timeout=8, check=False, start_new_session=True)
            except subprocess.TimeoutExpired as exc:
                raise ValueError('Test execution exceeded 8 seconds; no changes were kept.') from exc
            logs.seek(0)
            output = logs.read(24_000).decode(errors='replace')
        if not report.exists() or result.returncode != 0:
            raise ValueError('The test runner failed; no changes were kept.')
        evidence = json.loads(report.read_text(encoding='utf-8'))
        states = evidence['states']
        return {'passing': sorted(k for k,v in states.items() if v == 'passed'), 'failing': sorted(k for k,v in states.items() if v == 'failed'), 'skipped': sorted(k for k,v in states.items() if v == 'skipped'), 'errors': evidence['errors'], 'test_files': test_files, 'mode': 'pytest', 'exit_code': evidence['exit_code'], 'output': output, 'valid': evidence['exit_code'] in (0, 1) and not evidence['errors'] and bool(states)}


def decide(baseline: dict, after: dict) -> dict:
    if baseline.get('mode') == 'static':
        accepted = bool(after['valid'] and after.get('mode') == 'pytest' and after.get('test_files') and after['passing'] and not after['failing'] and not after['errors'])
        reason = 'No original pytest suite existed. The repair added regression tests and all candidate tests passed.' if accepted else 'No original test suite existed. A repair is accepted only after adding meaningful pytest regression tests that pass.'
        return {'accepted': accepted, 'regressions': [], 'reason': reason}
    regressions = sorted(set(baseline['passing']) - set(after['passing']))
    missing = sorted((set(baseline['passing']) | set(baseline['failing'])) - (set(after['passing']) | set(after['failing'])))
    improved = len(after['failing']) < len(baseline['failing']) or not after['failing']
    recovered_collection = bool(baseline.get('errors') and after['valid'] and not after['failing'])
    accepted = bool(after['valid'] and not regressions and not missing and ((baseline['valid'] and improved) or recovered_collection))
    reason = 'Zero regressions. All baseline tests retained; failures reduced or all tests pass.' if accepted else 'Discarded: regression, missing/skipped test, invalid suite, or no reduction in failures.'
    return {'accepted': accepted, 'regressions': regressions, 'reason': reason}


def verify(files: dict, edits: list, baseline: dict | None = None) -> dict:
    candidate = apply_edits(files, edits)
    before = run_tests(files)
    after = run_tests(candidate)
    diff = ''.join(''.join(difflib.unified_diff(files.get(path, '').splitlines(True), candidate[path].splitlines(True), fromfile='a/'+path, tofile='b/'+path)) for path in candidate if files.get(path) != candidate[path])
    return {**decide(before, after), 'baseline': before, 'after': after, 'diff': diff, 'files_changed': [p for p in candidate if candidate[p] != files.get(p)]}
