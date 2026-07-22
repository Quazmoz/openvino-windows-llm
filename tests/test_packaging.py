import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_hugging_face_search_http_client_is_a_runtime_dependency():
    project_dependencies = _pyproject()["project"]["dependencies"]
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

    assert any(dependency.startswith("httpx") for dependency in project_dependencies)
    assert any(line.strip().startswith("httpx") for line in requirements)


def test_setuptools_discovers_advisor_and_future_subpackages():
    find_config = _pyproject()["tool"]["setuptools"]["packages"]["find"]

    assert "app*" in find_config["include"]
    assert "runtime*" in find_config["include"]
