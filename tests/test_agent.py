import json
from types import SimpleNamespace
import pytest
from agent.core import apply_edits, decide, parse_proposal, run_tests, validate_files, verify
from agent.github import import_github
from agent.model import OpenRouterModels, check_openrouter, generate, propose, status

PROJECT = {
    "app.py": "def add(left, right):\n    return left - right\n",
    "tests/test_app.py": "from app import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
}
FIXED = "def add(left, right):\n    return left + right\n"


def local_runner(monkeypatch):
    monkeypatch.setenv("ALLOW_TRUSTED_CODE", "1")
    monkeypatch.delenv("VERCEL", raising=False)


def test_local_end_to_end_verification(monkeypatch):
    local_runner(monkeypatch)
    before = run_tests(PROJECT)
    assert before["valid"] and len(before["failing"]) == 1
    result = verify(PROJECT, [{"file": "app.py", "content": FIXED}], before)
    assert result["accepted"] and result["regressions"] == []
    assert len(result["after"]["passing"]) == 1 and result["diff"]


def test_hosted_custom_execution_is_blocked(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("ALLOW_TRUSTED_CODE", "1")
    with pytest.raises(ValueError, match="hosted execution"):
        run_tests({"test_app.py": "def test_ok(): assert True"})


def test_local_execution_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("ALLOW_TRUSTED_CODE", raising=False)
    with pytest.raises(ValueError, match="Code execution is disabled"):
        run_tests({"test_app.py": "def test_ok(): assert True"})


def test_missing_pytest_suite_runs_safe_static_diagnostics(monkeypatch):
    monkeypatch.setenv("ALLOW_TRUSTED_CODE", "0")
    evidence = run_tests({"app.py": "def add(a, b): return a + b"})
    assert evidence["valid"] and evidence["mode"] == "static"
    assert evidence["test_files"] == [] and evidence["failing"] == []
    assert "No pytest files found" in evidence["output"]


def test_missing_pytest_suite_reports_exact_syntax_error():
    evidence = run_tests({"app.py": "def add(a, b)\n    return a + b\n"})
    assert evidence["valid"] and evidence["mode"] == "static"
    assert evidence["failing"] == ["syntax::app.py"]
    assert "app.py:1:" in evidence["output"] and "SyntaxError" in evidence["output"]


def test_testless_repair_requires_and_accepts_new_passing_regression_test(monkeypatch):
    local_runner(monkeypatch)
    source = {"app.py": "def add(a, b): return a - b\n"}
    before = run_tests(source)
    edits = [
        {"file": "app.py", "content": "def add(a, b): return a + b\n"},
        {"file": "tests/test_repair.py", "content": "from app import add\n\ndef test_add_uses_sum():\n    assert add(2, 3) == 5\n"},
    ]
    result = verify(source, edits, before)
    assert result["accepted"]
    assert result["after"]["test_files"] == ["tests/test_repair.py"]
    assert result["after"]["passing"] and not result["after"]["failing"]


def test_testless_repair_without_pytest_evidence_is_not_accepted(monkeypatch):
    local_runner(monkeypatch)
    source = {"app.py": "def add(a, b): return a - b\n"}
    result = verify(source, [{"file": "app.py", "content": "def add(a, b): return a + b\n"}], run_tests(source))
    assert not result["accepted"]
    assert "meaningful pytest regression tests" in result["reason"]


def test_collection_error_can_be_repaired(monkeypatch):
    local_runner(monkeypatch)
    broken = {
        "app.py": "def add(a, b)\n    return a + b\n",
        "tests/test_app.py": "from app import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    }
    before = run_tests(broken)
    assert not before["valid"] and before["errors"]
    result = verify(broken, [{"file": "app.py", "content": "def add(a, b):\n    return a + b\n"}], before)
    assert result["accepted"] and result["after"]["valid"]


@pytest.mark.parametrize("path", ["../escape.py", "/tmp/escape.py", "a/../../x.py", "a\\b.py", "a//b.py", ".hidden.py", "x.txt"])
def test_invalid_python_paths(path):
    with pytest.raises(ValueError):
        apply_edits(PROJECT, [{"file": path, "content": "pass"}])


def test_existing_tests_are_protected():
    with pytest.raises(ValueError, match="protected"):
        apply_edits(PROJECT, [{"file": "tests/test_app.py", "content": "pass"}])


def test_new_test_file_is_allowed():
    assert "tests/test_new.py" in apply_edits(PROJECT, [{"file": "tests/test_new.py", "content": "def test_new(): assert True"}])


@pytest.mark.parametrize("text", ["broken", "[]", '{"edits":[]}', "```json\nnope\n```"])
def test_bad_model_json_is_rejected(text):
    with pytest.raises(ValueError):
        parse_proposal(text)


def test_fenced_json_is_parsed():
    assert parse_proposal('```json\n{"explanation":"x","edits":[]}\n```')["explanation"] == "x"


def test_regression_gate_rejects_lost_passes():
    result = decide({"passing": ["kept"], "failing": ["broken"], "valid": True}, {"passing": [], "failing": [], "valid": True})
    assert not result["accepted"] and result["regressions"] == ["kept"]


def test_invalid_suite_is_rejected():
    assert not decide({"passing": ["a"], "failing": ["b"], "valid": True}, {"passing": ["a"], "failing": [], "valid": False})["accepted"]


def test_no_progress_is_rejected():
    evidence = {"passing": ["a"], "failing": ["b"], "valid": True}
    assert not decide(evidence, evidence)["accepted"]


def test_size_limit():
    with pytest.raises(ValueError, match="200 KB"):
        validate_files({"app.py": "x" * 200001})


def test_file_count_limit():
    with pytest.raises(ValueError, match="50 Python files"):
        validate_files({f"src/file_{n}.py": "" for n in range(51)})


def test_duplicate_edits_are_rejected():
    edit = {"file": "app.py", "content": "x"}
    with pytest.raises(ValueError, match="Duplicate"):
        apply_edits(PROJECT, [edit, edit])


def test_subprocess_does_not_receive_api_secrets(monkeypatch):
    local_runner(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-not-a-real-key")
    evidence = run_tests({"tests/test_env.py": 'import os\ndef test_no_key():\n    assert "OPENROUTER_API_KEY" not in os.environ\n'})
    assert evidence["valid"] and len(evidence["passing"]) == 1


def test_proposals_require_a_configured_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenRouter is not configured"):
        propose({"files": PROJECT, "task": "Fix the failing test"})


def test_proposal_prompt_adds_regression_for_uncovered_user_behavior(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-not-a-real-key")
    prompts = []
    def fake_generate(client, prompt, deadline):
        prompts.append(prompt)
        result = {"explanation": "The operation is incorrect.", "edits": [{"file": "app.py", "content": FIXED}, {"file": "tests/test_regression.py", "content": "from app import add\n\ndef test_add_positive(): assert add(2, 3) == 5\n"}]}
        return json.dumps(result), "vendor/free-model:free"
    monkeypatch.setattr("agent.model.generate", fake_generate)
    propose({"files": PROJECT, "task": "add(2, 3) must return 5; add a regression for it"})
    assert "add a new regression test for the explicitly described expected behavior" in prompts[0]


def test_status_reports_key_and_safe_runner_state(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-not-a-real-key")
    monkeypatch.setenv("ALLOW_TRUSTED_CODE", "1")
    monkeypatch.delenv("VERCEL", raising=False)
    value = status()
    assert value["openrouter_configured"] and value["execution_enabled"]


def test_openrouter_check_fails_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="not configured"):
        check_openrouter()


def test_openrouter_check_uses_server_side_client(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-not-a-real-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    calls = []
    fake = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: calls.append(kwargs) or SimpleNamespace(text="OK")))
    assert check_openrouter(fake)["connected"]
    assert calls[0]["model"] == "openrouter/free"
    assert "OK" in calls[0]["contents"]


def test_model_retry_uses_fallback(monkeypatch):
    monkeypatch.setattr("agent.model.time.sleep", lambda _: None)
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODEL", "vendor/coder:free")
    calls = []
    class Busy(Exception):
        code = 503
    def call(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) <= 3:
            raise Busy()
        return SimpleNamespace(text="{}")
    client = SimpleNamespace(models=SimpleNamespace(generate_content=call))
    assert generate(client, "prompt")[1] == "vendor/coder:free"
    assert len(calls) == 4


def test_model_not_found_discovers_available_flash(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/free")
    class Missing(Exception):
        code = 404
    def call(**kwargs):
        if kwargs["model"] != "vendor/current-coder:free":
            raise Missing()
        return SimpleNamespace(text="{}")
    client = SimpleNamespace(models=SimpleNamespace(generate_content=call, list=lambda: [SimpleNamespace(name="vendor/current-coder:free", supported_actions=["chat.completions"])]))
    assert generate(client, "prompt")[1] == "vendor/current-coder:free"


def test_github_import_accepts_only_public_repo_roots():
    with pytest.raises(ValueError, match="Only public https"):
        import_github("https://example.com/owner/repo")
    with pytest.raises(ValueError, match="repository root"):
        import_github("https://github.com/owner/repo/tree/main")


class FakeResponse:
    def __init__(self, body):
        self.body = body
        self.status = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, amount=-1):
        return self.body[:amount] if amount >= 0 else self.body


def test_openrouter_request_uses_bearer_auth_and_json_mode(monkeypatch):
    payload = {"model": "vendor/coder:free", "choices": [{"message": {"content": "{}"}}]}
    requests = []
    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse(json.dumps(payload).encode())
    monkeypatch.setattr("agent.model.urlopen", fake_urlopen)
    response = OpenRouterModels("server-token-only").generate_content(
        "openrouter/free", "Fix the failing test", {"response_mime_type": "application/json", "max_output_tokens": 48, "temperature": 0.1}
    )
    assert response.text == "{}" and response.model == "vendor/coder:free"
    request = requests[0]
    body = json.loads(request.data)
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer server-token-only"
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 48 and "server-token-only" not in request.data.decode()


def test_openrouter_model_discovery_returns_only_free_models(monkeypatch):
    payload = {"data": [
        {"id": "vendor/free-coder:free", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "vendor/paid-coder", "pricing": {"prompt": "0.01", "completion": "0.02"}},
    ]}
    monkeypatch.setattr("agent.model.urlopen", lambda request, timeout: FakeResponse(json.dumps(payload).encode()))
    models = OpenRouterModels("server-token-only").list()
    assert [model.name for model in models] == ["vendor/free-coder:free"]


def test_github_import_fetches_python_only_with_bounded_tree(monkeypatch):
    metadata = {"default_branch": "main", "full_name": "owner/repo"}
    tree = {"truncated": False, "tree": [
        {"path": "app.py", "type": "blob", "mode": "100644"},
        {"path": "tests/test_app.py", "type": "blob", "mode": "100644"},
        {"path": "README.md", "type": "blob", "mode": "100644"},
        {"path": ".github/action.py", "type": "blob", "mode": "100644"},
        {"path": "link.py", "type": "blob", "mode": "120000"},
    ]}
    bodies = {
        "https://api.github.com/repos/owner/repo": json.dumps(metadata).encode(),
        "https://api.github.com/repos/owner/repo/git/trees/main?recursive=1": json.dumps(tree).encode(),
        "https://raw.githubusercontent.com/owner/repo/main/app.py": b"def value(): return 1\n",
        "https://raw.githubusercontent.com/owner/repo/main/tests/test_app.py": b"def test_value(): assert True\n",
    }
    requested = []
    def fake_urlopen(request, timeout):
        requested.append(request.full_url)
        if request.full_url not in bodies:
            raise AssertionError(f"unexpected request: {request.full_url}")
        return FakeResponse(bodies[request.full_url])
    monkeypatch.setattr("agent.github.urlopen", fake_urlopen)
    result = import_github("https://github.com/owner/repo.git")
    assert result["name"] == "owner/repo"
    assert set(result["files"]) == {"app.py", "tests/test_app.py"}
    assert not any(url.endswith("/.github/action.py") or url.endswith("/link.py") for url in requested)


def test_github_import_rejects_truncated_repository(monkeypatch):
    metadata = {"default_branch": "main", "full_name": "owner/repo"}
    tree = {"truncated": True, "tree": []}
    bodies = [json.dumps(metadata).encode(), json.dumps(tree).encode()]
    monkeypatch.setattr("agent.github.urlopen", lambda request, timeout: FakeResponse(bodies.pop(0)))
    with pytest.raises(ValueError, match="too large to import"):
        import_github("https://github.com/owner/repo")
