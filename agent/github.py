"""Read-only importer for public GitHub repositories; never checks out or runs code."""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

MAX_FILES = 50
MAX_BYTES = 200_000
MAX_TREE_RESPONSE = 2_000_000
SKIP_DIRS = {'.git', '.github', '.venv', 'venv', 'env', '__pycache__', 'node_modules', 'vendor', 'dist', 'build', 'site-packages'}


def _repository(url: str) -> tuple[str, str]:
    if not isinstance(url, str) or len(url) > 500:
        raise ValueError('Enter a public GitHub repository URL.')
    parsed = urlparse(url.strip())
    if parsed.scheme != 'https' or parsed.hostname not in {'github.com', 'www.github.com'} or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.query or parsed.fragment:
        raise ValueError('Only public https://github.com/owner/repository URLs are supported.')
    parts = [part for part in parsed.path.split('/') if part]
    if len(parts) == 2 and parts[1].endswith('.git'):
        parts[1] = parts[1][:-4]
    if len(parts) != 2 or not all(re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', part) for part in parts):
        raise ValueError('Use a repository root URL such as https://github.com/owner/repository.')
    if parts[0] in {'.', '..'} or parts[1] in {'.', '..'}:
        raise ValueError('Invalid GitHub repository path.')
    return parts[0], parts[1]


def _get(url: str, limit: int, timeout: int = 10) -> bytes:
    request = Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'Sentinel-Workspace/1.0', 'X-GitHub-Api-Version': '2022-11-28'})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(limit + 1)
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError('GitHub repository or file was not found; make sure the repository is public.') from None
        if exc.code == 403 or exc.code == 429:
            raise ValueError('GitHub rate limit reached. Try again later.') from None
        raise ValueError(f'GitHub request failed with HTTP {exc.code}.') from None
    except (URLError, TimeoutError, OSError):
        raise ValueError('Could not connect to GitHub. Check the URL and network connection.') from None
    if len(body) > limit:
        raise ValueError('GitHub response exceeds the import size limit.')
    return body


def import_github(url: str) -> dict:
    owner, repo = _repository(url)
    base = f'https://api.github.com/repos/{quote(owner)}/{quote(repo)}'
    try:
        metadata = json.loads(_get(base, 128_000).decode('utf-8'))
        branch = metadata['default_branch']
        full_name = metadata['full_name']
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
        raise ValueError('GitHub returned invalid repository metadata.') from None
    if not isinstance(branch, str) or not branch:
        raise ValueError('GitHub repository has no default branch.')
    branch_path = quote(branch, safe='/')
    try:
        tree = json.loads(_get(f'{base}/git/trees/{branch_path}?recursive=1', MAX_TREE_RESPONSE).decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError('GitHub returned an invalid repository file tree.') from None
    if tree.get('truncated'):
        raise ValueError('This repository tree is too large to import safely. Import a smaller repository or add files manually.')
    candidates = []
    for item in tree.get('tree', []):
        path = item.get('path', '')
        if item.get('type') != 'blob' or item.get('mode') not in {'100644', '100755'} or not path.endswith('.py'):
            continue
        pieces = path.split('/')
        if any(piece.startswith('.') or piece in SKIP_DIRS for piece in pieces[:-1]):
            continue
        if pieces[-1].startswith('.'):
            continue
        candidates.append(path)
    candidates.sort(key=lambda p: (not p.startswith(('tests/', 'test/')), p))
    if not candidates:
        raise ValueError('No Python source files were found in this public repository.')
    if len(candidates) > MAX_FILES:
        raise ValueError(f'Repository contains more than {MAX_FILES} importable Python files. Import a smaller project.')
    def fetch(path):
        raw_url = f'https://raw.githubusercontent.com/{quote(owner)}/{quote(repo)}/{branch_path}/' + '/'.join(quote(part, safe='') for part in path.split('/'))
        return path, _get(raw_url, MAX_BYTES, timeout=5)

    files = {}
    size = 0
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(fetch, path) for path in candidates]
            for future in as_completed(futures, timeout=35):
                path, body = future.result()
                try:
                    content = body.decode('utf-8')
                except UnicodeDecodeError:
                    continue
                size += len(body)
                if size > MAX_BYTES:
                    raise ValueError('Imported Python files exceed the 200 KB total limit.')
                files[path] = content
    except FuturesTimeoutError:
        raise ValueError('GitHub file import timed out. Try a smaller repository or retry shortly.') from None
    if not files:
        raise ValueError('No UTF-8 Python files were found in this repository.')
    return {'name': full_name, 'default_branch': branch, 'files': files, 'source_url': f'https://github.com/{owner}/{repo}'}
