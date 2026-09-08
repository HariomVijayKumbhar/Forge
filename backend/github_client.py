import re
import base64
import json
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timezone
import httpx
import logging
from backend.config import settings

logger = logging.getLogger("forge.github")


def parse_github_url(repo_url: str) -> Tuple[str, str]:
    """Extracts (owner, repo) from a GitHub repository URL."""
    cleaned = repo_url.rstrip("/").replace(".git", "")
    match = re.search(r"github\.com[/:]([\w\-]+)/([\w\-]+)", cleaned)
    if not match:
        raise ValueError(f"Invalid GitHub repository URL: {repo_url}")
    return match.group(1), match.group(2)


class GitHubClient:
    """
    GitHub API client for read-only issue/PR lookups and gated PR creation.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Forge-Autonomous-Agent",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_issue_or_pr(self, repo_url: str, item_number: int, item_type: str = "issue") -> str:
        """Fetches issue or pull request details from public repository."""
        try:
            owner, repo = parse_github_url(repo_url)
        except Exception as e:
            return f"Failed to parse repo URL: {e}"

        endpoint = f"https://api.github.com/repos/{owner}/{repo}/issues/{item_number}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(endpoint, headers=self._headers())
                if response.status_code == 404:
                    return f"GitHub item #{item_number} not found in {owner}/{repo}."
                if response.status_code != 200:
                    return f"GitHub API error ({response.status_code}): {response.text}"

                data = response.json()
                title = data.get("title", "")
                body = data.get("body", "")
                user = data.get("user", {}).get("login", "unknown")
                state = data.get("state", "unknown")
                is_pr = "pull_request" in data

                # Fetch comments if available
                comments_text = ""
                comments_url = data.get("comments_url")
                if comments_url and data.get("comments", 0) > 0:
                    comm_resp = await client.get(comments_url, headers=self._headers())
                    if comm_resp.status_code == 200:
                        comments = comm_resp.json()
                        comments_text = "\nComments:\n" + "\n".join(
                            f"- @{c.get('user', {}).get('login')}: {c.get('body', '')[:300]}"
                            for c in comments[:3]
                        )

                return (
                    f"=== GitHub #{item_number} ({'PR' if is_pr else 'Issue'}) [{state.upper()}] ===\n"
                    f"Title: {title}\nAuthor: @{user}\nDescription:\n{body}\n{comments_text}"
                )
            except Exception as e:
                return f"Error contacting GitHub API: {e}"

    async def create_pull_request(
        self,
        repo_url: str,
        title: str,
        body: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
        """
        Creates a Pull Request on GitHub. Requires GITHUB_TOKEN with repository write scope.
        """
        if not self.token:
            raise PermissionError("GITHUB_TOKEN is not configured on the backend server.")

        owner, repo = parse_github_url(repo_url)
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": branch_name,
            "base": base_branch,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "success": True,
                    "pr_url": data.get("html_url"),
                    "pr_number": data.get("number"),
                }
            else:
                error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                return {
                    "success": False,
                    "error": f"GitHub API rejected PR creation ({response.status_code}): {error_detail}",
                }

    # ==================== 🔗 GitHub Issues Auto-Assignment ====================
    
    async def link_run_to_issue(
        self,
        repo_url: str,
        issue_number: int,
        run_id: str,
        status: str = "in_progress",
    ) -> Dict[str, Any]:
        """Link a run to a GitHub issue and optionally assign/comment."""
        if not self.token:
            return {"success": False, "error": "GITHUB_TOKEN not configured"}
        
        owner, repo = parse_github_url(repo_url)
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        
        # Create a comment linking the run
        comment_url = f"{url}/comments"
        comment_body = f"🤖 **Forge Agent Started**\nRun ID: `{run_id}`\nStatus: {status}"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                comment_url,
                headers=self._headers(),
                json={"body": comment_body}
            )
            return {
                "success": resp.status_code in [200, 201],
                "run_id": run_id,
                "issue_number": issue_number,
                "comment_url": resp.json().get("html_url") if resp.status_code in [200, 201] else None,
            }

    async def close_issue_with_run_result(
        self,
        repo_url: str,
        issue_number: int,
        run_id: str,
        summary: str,
        success: bool,
    ) -> Dict[str, Any]:
        """Close an issue and add a comment with run results."""
        if not self.token:
            return {"success": False, "error": "GITHUB_TOKEN not configured"}
        
        owner, repo = parse_github_url(repo_url)
        issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        
        # Update issue status
        status_emoji = "✅" if success else "❌"
        comment_body = (
            f"{status_emoji} **Forge Run Complete**\n"
            f"Run ID: `{run_id}`\n"
            f"Status: {'Success' if success else 'Failed'}\n\n"
            f"**Summary:**\n{summary}"
        )
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Add comment
            comment_resp = await client.post(
                f"{issue_url}/comments",
                headers=self._headers(),
                json={"body": comment_body}
            )
            
            # Close issue if successful
            if success:
                close_resp = await client.patch(
                    issue_url,
                    headers=self._headers(),
                    json={"state": "closed"}
                )
                return {
                    "success": close_resp.status_code in [200, 201],
                    "closed": True,
                    "comment_url": comment_resp.json().get("html_url") if comment_resp.status_code in [200, 201] else None,
                }
        
        return {
            "success": comment_resp.status_code in [200, 201],
            "closed": False,
            "comment_url": comment_resp.json().get("html_url") if comment_resp.status_code in [200, 201] else None,
        }

    # ==================== 💾 GitHub Commit Integration ====================
    
    async def create_commit(
        self,
        repo_url: str,
        branch_name: str,
        file_changes: Dict[str, str],  # {filepath: content}
        commit_message: str,
        author_name: str = "Forge Agent",
    ) -> Dict[str, Any]:
        """Create a commit with multiple file changes using GitHub API."""
        if not self.token:
            return {"success": False, "error": "GITHUB_TOKEN not configured"}
        
        owner, repo = parse_github_url(repo_url)
        base_url = f"https://api.github.com/repos/{owner}/{repo}"
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Get the branch reference
                ref_url = f"{base_url}/git/refs/heads/{branch_name}"
                ref_resp = await client.get(ref_url, headers=self._headers())
                if ref_resp.status_code != 200:
                    return {"success": False, "error": f"Branch {branch_name} not found"}
                
                branch_sha = ref_resp.json()["object"]["sha"]
                
                # Get the commit tree
                commit_url = f"{base_url}/git/commits/{branch_sha}"
                commit_resp = await client.get(commit_url, headers=self._headers())
                tree_sha = commit_resp.json()["tree"]["sha"]
                
                # Create new tree with file changes
                tree_items = []
                for filepath, content in file_changes.items():
                    tree_items.append({
                        "path": filepath,
                        "mode": "100644",
                        "type": "blob",
                        "content": content,
                    })
                
                tree_url = f"{base_url}/git/trees"
                tree_resp = await client.post(
                    tree_url,
                    headers=self._headers(),
                    json={
                        "base_tree": tree_sha,
                        "tree": tree_items,
                    }
                )
                if tree_resp.status_code != 201:
                    return {"success": False, "error": "Failed to create tree"}
                
                new_tree_sha = tree_resp.json()["sha"]
                
                # Create commit
                new_commit_resp = await client.post(
                    f"{base_url}/git/commits",
                    headers=self._headers(),
                    json={
                        "message": commit_message,
                        "tree": new_tree_sha,
                        "parents": [branch_sha],
                        "author": {
                            "name": author_name,
                            "email": "forge@autonomous.dev",
                            "date": datetime.now(timezone.utc).isoformat(),
                        }
                    }
                )
                if new_commit_resp.status_code != 201:
                    return {"success": False, "error": "Failed to create commit"}
                
                new_commit_sha = new_commit_resp.json()["sha"]
                
                # Update branch reference
                update_resp = await client.patch(
                    ref_url,
                    headers=self._headers(),
                    json={"sha": new_commit_sha}
                )
                
                return {
                    "success": update_resp.status_code in [200, 201],
                    "commit_sha": new_commit_sha,
                    "branch": branch_name,
                    "files_changed": len(file_changes),
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== 📊 Repository Metadata & Insights ====================
    
    async def get_repo_metadata(self, repo_url: str) -> Dict[str, Any]:
        """Fetch comprehensive repository metadata and insights."""
        try:
            owner, repo = parse_github_url(repo_url)
        except Exception as e:
            return {"error": str(e)}
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                repo_resp = await client.get(api_url, headers=self._headers())
                if repo_resp.status_code != 200:
                    return {"error": f"Repository not found (status {repo_resp.status_code})"}
                
                repo_data = repo_resp.json()
                
                # Get languages
                langs_resp = await client.get(f"{api_url}/languages", headers=self._headers())
                languages = langs_resp.json() if langs_resp.status_code == 200 else {}
                
                # Get contributors count
                contrib_resp = await client.get(
                    f"{api_url}/contributors?per_page=1",
                    headers=self._headers()
                )
                contributors_count = 0
                if contrib_resp.status_code == 200:
                    link_header = contrib_resp.headers.get("link", "")
                    if 'last' in link_header:
                        last_url = [l for l in link_header.split(",") if 'rel="last"' in l]
                        if last_url:
                            match = re.search(r'page=(\d+)', last_url[0])
                            if match:
                                contributors_count = int(match.group(1))
                    else:
                        contributors_count = len(contrib_resp.json())
                
                return {
                    "success": True,
                    "name": repo_data.get("name"),
                    "full_name": repo_data.get("full_name"),
                    "description": repo_data.get("description"),
                    "stars": repo_data.get("stargazers_count", 0),
                    "forks": repo_data.get("forks_count", 0),
                    "watchers": repo_data.get("watchers_count", 0),
                    "open_issues": repo_data.get("open_issues_count", 0),
                    "language": repo_data.get("language"),
                    "languages": languages,
                    "contributors": contributors_count,
                    "created_at": repo_data.get("created_at"),
                    "updated_at": repo_data.get("updated_at"),
                    "pushed_at": repo_data.get("pushed_at"),
                    "is_private": repo_data.get("private", False),
                    "is_fork": repo_data.get("fork", False),
                    "url": repo_data.get("html_url"),
                }
            except Exception as e:
                return {"error": str(e)}

    # ==================== 📝 GitHub Release Notes Generator ====================
    
    async def generate_release_notes(
        self,
        repo_url: str,
        run_ids: List[str],
        version: str,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
        """Generate release notes from completed runs."""
        try:
            owner, repo = parse_github_url(repo_url)
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        release_body = f"# Release {version}\n\n"
        release_body += f"**Generated by Forge Autonomous Agent**\n"
        release_body += f"**Date:** {datetime.now(timezone.utc).isoformat()}\n\n"
        release_body += "## Changes\n"
        
        for run_id in run_ids:
            release_body += f"- Run: `{run_id}`\n"
        
        if not self.token:
            return {"success": False, "error": "GITHUB_TOKEN not configured"}
        
        releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                releases_url,
                headers=self._headers(),
                json={
                    "tag_name": f"v{version}",
                    "target_commitish": base_branch,
                    "name": f"Release {version}",
                    "body": release_body,
                    "draft": False,
                    "prerelease": False,
                }
            )
            
            if resp.status_code in [200, 201]:
                data = resp.json()
                return {
                    "success": True,
                    "release_url": data.get("html_url"),
                    "release_id": data.get("id"),
                    "version": version,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create release (status {resp.status_code})",
                }

    # ==================== 💬 GitHub Discussions Integration ====================
    
    async def post_to_discussion(
        self,
        repo_url: str,
        category_name: str,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        """Post a discussion to GitHub Discussions (requires GraphQL)."""
        if not self.token:
            return {"success": False, "error": "GITHUB_TOKEN not configured"}
        
        try:
            owner, repo = parse_github_url(repo_url)
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        graphql_url = "https://api.github.com/graphql"
        
        # GraphQL query to create discussion
        query = """
        query($owner: String!, $repo: String!, $category: String!) {
            repository(owner: $owner, name: $repo) {
                discussionCategories(first: 10) {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # First, find category
            resp = await client.post(
                graphql_url,
                headers={
                    **self._headers(),
                    "X-Apollo-Tracing": "true",
                },
                json={
                    "query": query,
                    "variables": {
                        "owner": owner,
                        "repo": repo,
                        "category": category_name,
                    }
                }
            )
            
            if resp.status_code != 200:
                return {"success": False, "error": "Failed to fetch discussion categories"}
            
            data = resp.json()
            categories = data.get("data", {}).get("repository", {}).get("discussionCategories", {}).get("edges", [])
            category_id = None
            
            for edge in categories:
                if edge["node"]["name"].lower() == category_name.lower():
                    category_id = edge["node"]["id"]
                    break
            
            if not category_id:
                return {"success": False, "error": f"Discussion category '{category_name}' not found"}
            
            # Create discussion
            create_mutation = """
            mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
                createDiscussion(input: {repositoryId: $repositoryId, categoryId: $categoryId, title: $title, body: $body}) {
                    discussion {
                        id
                        url
                    }
                }
            }
            """
            
            # Get repo ID
            repo_query = """query($owner: String!, $repo: String!) {
                repository(owner: $owner, name: $repo) {
                    id
                }
            }"""
            
            repo_resp = await client.post(
                graphql_url,
                headers=self._headers(),
                json={
                    "query": repo_query,
                    "variables": {"owner": owner, "repo": repo}
                }
            )
            
            repo_data = repo_resp.json()
            repo_id = repo_data.get("data", {}).get("repository", {}).get("id")
            
            if not repo_id:
                return {"success": False, "error": "Could not fetch repository ID"}
            
            # Create discussion
            create_resp = await client.post(
                graphql_url,
                headers=self._headers(),
                json={
                    "query": create_mutation,
                    "variables": {
                        "repositoryId": repo_id,
                        "categoryId": category_id,
                        "title": title,
                        "body": body,
                    }
                }
            )
            
            create_data = create_resp.json()
            if "errors" in create_data:
                return {"success": False, "error": str(create_data["errors"])}
            
            discussion = create_data.get("data", {}).get("createDiscussion", {}).get("discussion", {})
            return {
                "success": True,
                "discussion_url": discussion.get("url"),
                "discussion_id": discussion.get("id"),
            }

    # ==================== 📦 GitHub Packages & Releases ====================
    
    async def create_release_with_assets(
        self,
        repo_url: str,
        version: str,
        release_notes: str,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
        """Create a GitHub release with comprehensive release information."""
        if not self.token:
            return {"success": False, "error": "GITHUB_TOKEN not configured"}
        
        try:
            owner, repo = parse_github_url(repo_url)
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                releases_url,
                headers=self._headers(),
                json={
                    "tag_name": f"v{version}",
                    "target_commitish": base_branch,
                    "name": f"Version {version}",
                    "body": release_notes,
                    "draft": False,
                    "prerelease": False,
                }
            )
            
            if resp.status_code in [200, 201]:
                release_data = resp.json()
                return {
                    "success": True,
                    "release_url": release_data.get("html_url"),
                    "release_id": release_data.get("id"),
                    "version": version,
                    "created_at": release_data.get("created_at"),
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create release ({resp.status_code})",
                }


github_client = GitHubClient()
