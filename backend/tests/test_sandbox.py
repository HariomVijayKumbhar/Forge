import pytest
import os
import tempfile
from pathlib import Path
from backend.sandbox import Sandbox, SandboxViolation


def test_sandbox_path_containment():
    run_id = "test_run_123"
    sandbox = Sandbox(run_id)
    try:
        # Valid relative paths
        valid_path = sandbox.validate_path("src/index.js")
        assert valid_path.is_relative_to(sandbox.workspace_dir)

        valid_nested = sandbox.validate_path("nested/deep/file.py")
        assert valid_nested.is_relative_to(sandbox.workspace_dir)

        # Directory traversal attacks (must be blocked)
        with pytest.raises(SandboxViolation):
            sandbox.validate_path("../outside.py")

        with pytest.raises(SandboxViolation):
            sandbox.validate_path("../../etc/passwd")

        with pytest.raises(SandboxViolation):
            sandbox.validate_path("....//....//secret.env")

    finally:
        sandbox.cleanup()


def test_sandbox_file_operations():
    run_id = "test_run_file_ops"
    sandbox = Sandbox(run_id)
    try:
        # Write file
        msg = sandbox.write_file("main.py", "def add(a, b):\n    return a + b\n")
        assert "Successfully wrote" in msg

        # Read file
        content = sandbox.read_file("main.py")
        assert "def add(a, b):" in content
        assert "return a + b" in content

        # Search code
        search_res = sandbox.search_code("add")
        assert "main.py:1: def add(a, b):" in search_res

    finally:
        sandbox.cleanup()


def test_sandbox_nonexistent_file_handling():
    run_id = "test_run_missing"
    sandbox = Sandbox(run_id)
    try:
        with pytest.raises(FileNotFoundError):
            sandbox.read_file("does_not_exist.txt")
    finally:
        sandbox.cleanup()
