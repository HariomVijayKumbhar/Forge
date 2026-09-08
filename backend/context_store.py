from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.llm.provider import AgentContext


class ContextStore:
    """
    Manages per-run context state (scratchpad, sliding observation window,
    active files list, and running history).
    """

    def __init__(self, run_id: str, repo_url: str, task: str, max_iterations: int = 25):
        self.run_id = run_id
        self.repo_url = repo_url
        self.task = task
        self.max_iterations = max_iterations
        self.iteration = 0
        self.plan: Optional[str] = None
        self.files_viewed: set[str] = set()
        self.files_modified: set[str] = set()
        self.observations: List[Dict[str, Any]] = []
        self.summarized_history: List[str] = []

    def record_file_view(self, path: str):
        self.files_viewed.add(path)

    def record_file_modification(self, path: str):
        self.files_modified.add(path)

    def add_observation(self, tool_name: str, tool_output: str, status: str = "ok"):
        self.observations.append({
            "tool": tool_name,
            "output": tool_output[:2000] if len(tool_output) > 2000 else tool_output,
            "status": status,
            "iteration": self.iteration,
        })
        # If observation count grows too large, summarize older ones
        if len(self.observations) > 8:
            older = self.observations[:-4]
            summary_item = f"Step {self.iteration}: executed {len(older)} tools ({', '.join(o['tool'] for o in older)})"
            self.summarized_history.append(summary_item)
            self.observations = self.observations[-4:]

    def to_agent_context(self) -> AgentContext:
        return AgentContext(
            task=self.task,
            repo_url=self.repo_url,
            plan=self.plan,
            files_viewed=sorted(list(self.files_viewed)),
            files_modified=sorted(list(self.files_modified)),
            recent_observations=self.observations,
            history_summary=" | ".join(self.summarized_history) if self.summarized_history else None,
            iteration=self.iteration,
            max_iterations=self.max_iterations,
        )
