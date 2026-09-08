from typing import Dict, Any, List, Optional
import shlex
from pydantic import BaseModel, Field, ValidationError
from backend.sandbox import Sandbox, SandboxViolation
from backend.llm.provider import ToolSchema


# --- Tool Argument Models ---
class ReadFileInput(BaseModel):
    path: str = Field(description="Relative path of the file to read")
    start_line: Optional[int] = Field(default=None, description="1-indexed starting line number")
    end_line: Optional[int] = Field(default=None, description="1-indexed ending line number")


class WriteFileInput(BaseModel):
    path: str = Field(description="Relative path of the file to write or create")
    content: str = Field(description="The complete file content to write")


class SearchCodeInput(BaseModel):
    query: str = Field(description="String or pattern to search for")
    path_pattern: Optional[str] = Field(default=None, description="Glob pattern to restrict search, e.g. '*.py'")


class RunTestsInput(BaseModel):
    test_command: str = Field(default="pytest", description="Test command to run inside sandbox, e.g. 'pytest', 'npm test'")


class RunLinterInput(BaseModel):
    linter_command: str = Field(default="ruff check .", description="Linter command to run inside sandbox, e.g. 'ruff check .', 'flake8'")


class GitDiffInput(BaseModel):
    pass


class GitHubLookupInput(BaseModel):
    item_number: int = Field(description="Issue or Pull Request number")
    item_type: str = Field(default="issue", description="Type: 'issue' or 'pr'")


# --- Tool Schemas for LLM ---
TOOLS_DEFINITIONS: List[ToolSchema] = [
    ToolSchema(
        name="read_file",
        description="Read the contents of a file in the repository workspace with optional line slice.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path of the file to read"},
                "start_line": {"type": "integer", "description": "Starting line number (1-indexed)"},
                "end_line": {"type": "integer", "description": "Ending line number (1-indexed)"},
            },
            "required": ["path"],
        },
    ),
    ToolSchema(
        name="write_file",
        description="Write or update a file in the repository workspace. Replaces the file with the given content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path of the file to write or create"},
                "content": {"type": "string", "description": "The complete content of the file"},
            },
            "required": ["path", "content"],
        },
    ),
    ToolSchema(
        name="search_code",
        description="Search code across files in the repository workspace for matching text or symbols.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term or token"},
                "path_pattern": {"type": "string", "description": "Glob filter, e.g. '*.py' or 'src/*'"},
            },
            "required": ["query"],
        },
    ),
    ToolSchema(
        name="run_tests",
        description="Run test suite in the isolated sandbox environment.",
        parameters={
            "type": "object",
            "properties": {
                "test_command": {"type": "string", "description": "Test command to execute, e.g. 'pytest' or 'npm test'"},
            },
        },
    ),
    ToolSchema(
        name="run_linter",
        description="Run code linter or type-checker in the isolated sandbox environment.",
        parameters={
            "type": "object",
            "properties": {
                "linter_command": {"type": "string", "description": "Linter command to execute, e.g. 'ruff check .'"},
            },
        },
    ),
    ToolSchema(
        name="git_diff",
        description="Inspect the current git diff of all modifications made so far.",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    ToolSchema(
        name="github_issue_pr_lookup",
        description="Fetch issue or pull request details and discussion from GitHub.",
        parameters={
            "type": "object",
            "properties": {
                "item_number": {"type": "integer", "description": "Issue or PR number"},
                "item_type": {"type": "string", "enum": ["issue", "pr"], "description": "Type of item"},
            },
            "required": ["item_number"],
        },
    ),
]


TOOL_INPUT_MODELS: Dict[str, type[BaseModel]] = {
    "read_file": ReadFileInput,
    "write_file": WriteFileInput,
    "search_code": SearchCodeInput,
    "run_tests": RunTestsInput,
    "run_linter": RunLinterInput,
    "git_diff": GitDiffInput,
    "github_issue_pr_lookup": GitHubLookupInput,
}


async def dispatch_tool(tool_name: str, tool_args: Dict[str, Any], sandbox: Sandbox, github_client_fn=None) -> str:
    """
    Validates tool arguments against schemas and dispatches execution to the sandbox.
    """
    if tool_name not in TOOL_INPUT_MODELS:
        raise ValueError(f"Unknown tool: '{tool_name}'")

    # Validate against Pydantic schema
    model = TOOL_INPUT_MODELS[tool_name]
    validated = model.model_validate(tool_args)

    if tool_name == "read_file":
        assert isinstance(validated, ReadFileInput)
        return sandbox.read_file(validated.path, validated.start_line, validated.end_line)

    elif tool_name == "write_file":
        assert isinstance(validated, WriteFileInput)
        return sandbox.write_file(validated.path, validated.content)

    elif tool_name == "search_code":
        assert isinstance(validated, SearchCodeInput)
        return sandbox.search_code(validated.query, validated.path_pattern)

    elif tool_name == "run_tests":
        assert isinstance(validated, RunTestsInput)
        cmd_args = shlex.split(validated.test_command)
        code, stdout, stderr = sandbox.run_command(cmd_args, timeout=60)
        status = "PASSED" if code == 0 else f"FAILED (exit code {code})"
        return f"=== Tests {status} ===\nStdout:\n{stdout}\nStderr:\n{stderr}"

    elif tool_name == "run_linter":
        assert isinstance(validated, RunLinterInput)
        cmd_args = shlex.split(validated.linter_command)
        code, stdout, stderr = sandbox.run_command(cmd_args, timeout=60)
        status = "PASSED (clean)" if code == 0 else f"ISSUES FOUND (exit code {code})"
        return f"=== Linter {status} ===\n{stdout}\n{stderr}"

    elif tool_name == "git_diff":
        return sandbox.git_diff()

    elif tool_name == "github_issue_pr_lookup":
        assert isinstance(validated, GitHubLookupInput)
        if github_client_fn:
            return await github_client_fn(validated.item_number, validated.item_type)
        return f"GitHub lookup for #{validated.item_number} ({validated.item_type}): [Mock details fetched]"

    raise ValueError(f"Unimplemented tool dispatcher for: {tool_name}")
