import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple
import logging

from backend.config import settings

logger = logging.getLogger("forge.sandbox")


class SandboxViolation(Exception):
    """Raised when an operation attempts to breach the sandbox boundary."""
    pass


class Sandbox:
    """
    Hardened Execution Sandbox providing isolation for repository operations.
    Supports Docker-based container execution with network isolation and resource limits,
    with an explicit, scrubbed subprocess fallback.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        # Ensure root sandbox directory exists
        self.root_temp_dir = Path(settings.SANDBOX_TEMP_ROOT).resolve()
        self.root_temp_dir.mkdir(parents=True, exist_ok=True)

        # Unique isolated workspace for this specific run
        self.workspace_dir = (self.root_temp_dir / f"run_{run_id}").resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        self.container_id: Optional[str] = None
        self.is_docker_available: bool = False
        self._check_docker()

    def _check_docker(self):
        if not settings.ENABLE_DOCKER_SANDBOX:
            self.is_docker_available = False
            return
        try:
            import docker
            client = docker.from_env()
            client.ping()
            self.is_docker_available = True
            logger.info("Docker daemon verified for container isolation.")
        except Exception as e:
            self.is_docker_available = False
            logger.warning(f"Docker unavailable, using secure subprocess fallback: {e}")

    def validate_path(self, relative_path: str) -> Path:
        """
        Validates that the target path strictly resides within the run's workspace.
        Protects against directory traversal (../), absolute escapes, and symlink exploits.
        """
        if not relative_path or not relative_path.strip():
            raise SandboxViolation("Path cannot be empty.")

        # Check for forbidden traversal tokens or null bytes
        if "\0" in relative_path or ".." in relative_path:
            raise SandboxViolation(f"Access denied: Path '{relative_path}' contains forbidden traversal sequences.")

        # Clean relative path
        rel = relative_path.strip().lstrip("/\\")
        target_path = (self.workspace_dir / rel).resolve()

        # Check canonical containment
        try:
            target_path.relative_to(self.workspace_dir)
        except ValueError:
            raise SandboxViolation(f"Access denied: Path '{relative_path}' escapes sandbox workspace.")

        return target_path

    def clone_repo(self, repo_url: str) -> str:
        """Clones a public git repository shallowly into the sandbox workspace."""
        if not repo_url.startswith(("https://github.com/", "http://github.com/")):
            raise SandboxViolation("Only public GitHub repository URLs are supported.")

        logger.info(f"Cloning {repo_url} into {self.workspace_dir}")
        cmd = ["git", "clone", "--depth", "1", repo_url, str(self.workspace_dir)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed: {result.stderr.strip()}")
            return f"Successfully cloned {repo_url}"
        except subprocess.TimeoutExpired:
            raise TimeoutError("Repository clone timed out.")

    def read_file(self, relative_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """Reads a file with path containment verification and optional line slice."""
        target = self.validate_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File '{relative_path}' does not exist.")
        if target.is_dir():
            raise IsADirectoryError(f"'{relative_path}' is a directory, not a file.")

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            raise RuntimeError(f"Failed to read file: {e}")

        total_lines = len(lines)
        start = max(1, start_line) if start_line is not None else 1
        end = min(total_lines, end_line) if end_line is not None else total_lines

        if start > total_lines:
            return f"[File has {total_lines} lines. Requested start line {start} is out of bounds]"

        selected_lines = lines[start - 1 : end]
        content = "".join(f"{i + start:4d} | {line}" for i, line in enumerate(selected_lines))
        return f"=== File: {relative_path} (Lines {start}-{end} of {total_lines}) ===\n{content}"

    def write_file(self, relative_path: str, content: str) -> str:
        """Writes or creates a file with strict path containment verification."""
        target = self.validate_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to '{relative_path}'."

    def list_files(self, max_files: int = 200) -> str:
        # Return a bounded inventory of repository files for initial agent analysis."""
        files = []
        for file_path in self.workspace_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part.startswith(".") or part in {"node_modules", "venv", "__pycache__"} for part in file_path.parts):
                continue
            files.append(file_path.relative_to(self.workspace_dir).as_posix())
            if len(files) >= max_files:
                break
        files.sort()
        suffix = "\n[Inventory truncated]" if len(files) >= max_files else ""
        return "Repository files:\n" + "\n".join(files) + suffix
    def search_code(self, query: str, path_pattern: Optional[str] = None) -> str:
        """Searches repository code using ripgrep or Python regex scan."""
        matches = []
        pattern = path_pattern or "*"

        for file_path in self.workspace_dir.rglob(pattern):
            if file_path.is_file() and not any(part.startswith(".") or part in ["node_modules", "venv", "__pycache__"] for part in file_path.parts):
                try:
                    rel_path = file_path.relative_to(self.workspace_dir).as_posix()
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_idx, line in enumerate(f, start=1):
                            if query.lower() in line.lower():
                                matches.append(f"{rel_path}:{line_idx}: {line.strip()}")
                                if len(matches) >= 50:
                                    break
                except Exception:
                    continue
            if len(matches) >= 50:
                break

        if not matches:
            return f"No matches found for query: '{query}'"
        return f"Matches for '{query}':\n" + "\n".join(matches)

    def run_command(self, cmd_args: List[str], timeout: int = 60) -> Tuple[int, str, str]:
        """
        Executes a test or linter command inside the isolated environment.
        Uses Docker with --network none if available; otherwise uses a scrubbed subprocess environment.
        """
        # Whitelist permitted command runners
        allowed_runners = ["pytest", "python", "npm", "node", "cargo", "go", "mvn", "gradle", "ruff", "flake8", "eslint", "git"]
        base_cmd = cmd_args[0].lower().replace(".exe", "")
        if base_cmd not in allowed_runners:
            raise SandboxViolation(f"Command runner '{cmd_args[0]}' is not permitted in the sandbox.")

        if self.is_docker_available and settings.ENABLE_DOCKER_SANDBOX:
            return self._run_in_docker(cmd_args, timeout)
        else:
            return self._run_in_subprocess(cmd_args, timeout)

    def _run_in_subprocess(self, cmd_args: List[str], timeout: int) -> Tuple[int, str, str]:
        # Scrub sensitive environment variables
        scrubbed_env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "PYTHONUNBUFFERED": "1",
            "CI": "true",
        }

        try:
            proc = subprocess.run(
                cmd_args,
                cwd=str(self.workspace_dir),
                env=scrubbed_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Command timed out after {timeout} seconds.")
        except Exception as e:
            return 1, "", str(e)

    def _run_in_docker(self, cmd_args: List[str], timeout: int) -> Tuple[int, str, str]:
        import docker
        client = docker.from_env()
        container = None
        try:
            container = client.containers.run(
                image=settings.SANDBOX_DOCKER_IMAGE,
                command=cmd_args,
                volumes={str(self.workspace_dir): {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                network_mode="none",  # Strict network isolation
                mem_limit="512m",
                nano_cpus=1_000_000_000,  # 1 CPU
                detach=True,
                remove=False
            )
            result = container.wait(timeout=timeout)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            return result.get("StatusCode", 1), logs, ""
        except Exception as e:
            logger.error(f"Docker run error: {e}")
            return 1, "", str(e)
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def git_diff(self) -> str:
        """Returns the current git diff of changes in the sandbox repository."""
        try:
            proc = subprocess.run(
                ["git", "diff"],
                cwd=str(self.workspace_dir),
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            diff = proc.stdout
            if not diff.strip():
                # Check untracked files
                status_proc = subprocess.run(
                    ["git", "status", "--short"],
                    cwd=str(self.workspace_dir),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )
                if status_proc.stdout.strip():
                    diff = f"[Untracked files modified]\n{status_proc.stdout}"
            return diff
        except Exception as e:
            return f"Failed to get git diff: {e}"

    def cleanup(self):
        """Safely cleans up the ephemeral workspace directory."""
        try:
            if self.workspace_dir.exists():
                shutil.rmtree(self.workspace_dir, ignore_errors=True)
                logger.info(f"Cleaned up sandbox workspace {self.workspace_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up workspace {self.workspace_dir}: {e}")
