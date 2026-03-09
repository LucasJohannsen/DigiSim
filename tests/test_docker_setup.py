import pytest
import subprocess
import yaml
import os
from pathlib import Path


def is_docker_available():
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


docker_available = pytest.mark.skipif(
    not is_docker_available(),
    reason="Docker daemon not running"
)


@docker_available
def test_dockerfile_builds_successfully():
    result = subprocess.run(
        ["docker", "build", "-t", "digisim:test", "."],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    assert result.returncode == 0, f"Docker build failed: {result.stderr}"


@docker_available
def test_image_size_under_500mb():
    result = subprocess.run(
        ["docker", "images", "digisim:test", "--format", "{{.Size}}"],
        capture_output=True,
        text=True
    )
    size_str = result.stdout.strip()
    
    if "MB" in size_str:
        size_mb = float(size_str.replace("MB", "").strip())
    elif "GB" in size_str:
        size_gb = float(size_str.replace("GB", "").strip())
        size_mb = size_gb * 1024
    else:
        pytest.skip(f"Unexpected size format: {size_str}")
    
    assert size_mb < 500, f"Image size {size_mb}MB exceeds 500MB limit"


@docker_available
def test_dockerignore_excludes_tests():
    result = subprocess.run(
        ["docker", "run", "--rm", "digisim:test", "ls", "-la", "/app"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "tests" not in result.stdout, "tests/ directory should be excluded by .dockerignore"


def test_docker_compose_defines_volumes():
    compose_file = Path(__file__).parent.parent / "docker-compose.yml"
    with open(compose_file) as f:
        compose = yaml.safe_load(f)
    
    volumes = compose["services"]["digisim"]["volumes"]
    assert "./state:/app/state" in volumes
    assert "./retry_queue:/app/retry_queue" in volumes
    assert "./logs:/app/logs" in volumes
    assert "./config:/app/config:ro" in volumes


def test_docker_compose_has_healthcheck():
    compose_file = Path(__file__).parent.parent / "docker-compose.yml"
    with open(compose_file) as f:
        compose = yaml.safe_load(f)
    
    assert "healthcheck" in compose["services"]["digisim"]
    healthcheck = compose["services"]["digisim"]["healthcheck"]
    assert "test" in healthcheck
    assert "interval" in healthcheck
    assert "timeout" in healthcheck
    assert "retries" in healthcheck


@docker_available
@pytest.mark.integration
def test_container_starts_with_valid_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DIGIZERT_API_URL=http://test/\n"
        "DIGIZERT_API_TOKEN=test\n"
        "FARM_ID=7\n"
    )
    
    compose_file = tmp_path / "docker-compose.yml"
    compose_content = """
services:
  digisim:
    image: digisim:test
    container_name: digisim-test
    env_file: .env
    command: ["python", "-c", "import sys; sys.exit(0)"]
"""
    compose_file.write_text(compose_content)
    
    result = subprocess.run(
        ["docker-compose", "up", "-d"],
        cwd=tmp_path,
        capture_output=True,
        text=True
    )
    
    try:
        assert result.returncode == 0, f"docker-compose up failed: {result.stderr}"
    finally:
        subprocess.run(["docker-compose", "down"], cwd=tmp_path, capture_output=True)
