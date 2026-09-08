"""
GitHub Integration Routes for Forge
Provides endpoints for issue linking, commit creation, releases, and more
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth import verify_token
from backend.github_client import github_client
from backend.config import settings

router = APIRouter(prefix="/github", tags=["GitHub Integration"])


# ==================== Request Models ====================

class LinkRunToIssueRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    issue_number: int = Field(..., description="GitHub issue number")
    run_id: str = Field(..., description="Forge run ID")
    status: str = Field(default="in_progress", description="Current run status")


class CloseIssueRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    issue_number: int = Field(..., description="GitHub issue number")
    run_id: str = Field(..., description="Forge run ID")
    summary: str = Field(..., description="Run summary/results")
    success: bool = Field(..., description="Whether run was successful")


class CreateCommitRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    branch_name: str = Field(..., description="Branch to commit to")
    file_changes: Dict[str, str] = Field(..., description="Files to change: {filepath: content}")
    commit_message: str = Field(..., description="Commit message")
    author_name: str = Field(default="Forge Agent", description="Commit author name")


class GenerateReleaseNotesRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    run_ids: List[str] = Field(..., description="List of run IDs to include")
    version: str = Field(..., description="Release version number")
    base_branch: str = Field(default="main", description="Base branch for release")


class PostDiscussionRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    category_name: str = Field(..., description="Discussion category (e.g., 'Announcements')")
    title: str = Field(..., description="Discussion title")
    body: str = Field(..., description="Discussion body/content")


class CreateReleaseRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    version: str = Field(..., description="Release version")
    release_notes: str = Field(..., description="Release notes/body")
    base_branch: str = Field(default="main", description="Base branch for release")


# ==================== 🔗 Issues Auto-Assignment Endpoints ====================

@router.post("/issue/link")
async def link_run_to_issue(
    req: LinkRunToIssueRequest,
    current_user: dict = Depends(verify_token)
):
    """Link a Forge run to a GitHub issue with automatic commenting."""
    result = await github_client.link_run_to_issue(
        repo_url=req.repo_url,
        issue_number=req.issue_number,
        run_id=req.run_id,
        status=req.status
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    
    return result


@router.post("/issue/close")
async def close_issue_with_result(
    req: CloseIssueRequest,
    current_user: dict = Depends(verify_token)
):
    """Close a GitHub issue with Forge run results."""
    result = await github_client.close_issue_with_run_result(
        repo_url=req.repo_url,
        issue_number=req.issue_number,
        run_id=req.run_id,
        summary=req.summary,
        success=req.success
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail="Failed to close issue")
    
    return result


# ==================== 💾 Commit Integration Endpoints ====================

@router.post("/commit/create")
async def create_commit(
    req: CreateCommitRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a commit with file changes directly via GitHub API."""
    result = await github_client.create_commit(
        repo_url=req.repo_url,
        branch_name=req.branch_name,
        file_changes=req.file_changes,
        commit_message=req.commit_message,
        author_name=req.author_name
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create commit"))
    
    return result


# ==================== 📊 Repository Metadata Endpoints ====================

@router.get("/repo/metadata")
async def get_repo_metadata(
    repo_url: str = Query(..., description="GitHub repository URL"),
    current_user: dict = Depends(verify_token)
):
    """Get comprehensive repository metadata and insights."""
    result = await github_client.get_repo_metadata(repo_url)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/repo/languages")
async def get_repo_languages(
    repo_url: str = Query(..., description="GitHub repository URL"),
    current_user: dict = Depends(verify_token)
):
    """Get primary programming languages used in the repository."""
    metadata = await github_client.get_repo_metadata(repo_url)
    
    if "error" in metadata:
        raise HTTPException(status_code=400, detail=metadata["error"])
    
    return {
        "repo": repo_url,
        "primary_language": metadata.get("language"),
        "languages": metadata.get("languages", {}),
    }


@router.get("/repo/contributors")
async def get_repo_contributors(
    repo_url: str = Query(..., description="GitHub repository URL"),
    current_user: dict = Depends(verify_token)
):
    """Get repository contributor statistics."""
    metadata = await github_client.get_repo_metadata(repo_url)
    
    if "error" in metadata:
        raise HTTPException(status_code=400, detail=metadata["error"])
    
    return {
        "repo": repo_url,
        "total_contributors": metadata.get("contributors", 0),
        "stars": metadata.get("stars", 0),
        "forks": metadata.get("forks", 0),
    }


# ==================== 📝 Release Notes Endpoints ====================

@router.post("/release/generate-notes")
async def generate_release_notes(
    req: GenerateReleaseNotesRequest,
    current_user: dict = Depends(verify_token)
):
    """Generate release notes from completed runs."""
    result = await github_client.generate_release_notes(
        repo_url=req.repo_url,
        run_ids=req.run_ids,
        version=req.version,
        base_branch=req.base_branch
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to generate release notes"))
    
    return result


# ==================== 💬 Discussions Integration Endpoints ====================

@router.post("/discussion/post")
async def post_to_discussion(
    req: PostDiscussionRequest,
    current_user: dict = Depends(verify_token)
):
    """Post a new discussion to GitHub Discussions."""
    result = await github_client.post_to_discussion(
        repo_url=req.repo_url,
        category_name=req.category_name,
        title=req.title,
        body=req.body
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to post discussion"))
    
    return result


# ==================== 📦 Release Management Endpoints ====================

@router.post("/release/create")
async def create_release(
    req: CreateReleaseRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a GitHub release with comprehensive information."""
    result = await github_client.create_release_with_assets(
        repo_url=req.repo_url,
        version=req.version,
        release_notes=req.release_notes,
        base_branch=req.base_branch
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create release"))
    
    return result


# ==================== Info Endpoints ====================

@router.get("/status")
async def github_integration_status(
    current_user: dict = Depends(verify_token)
):
    """Get status of GitHub integration."""
    has_token = bool(settings.GITHUB_TOKEN)
    
    return {
        "status": "configured" if has_token else "unconfigured",
        "github_token_configured": has_token,
        "features": [
            "issues-auto-assignment",
            "commit-integration",
            "repo-metadata",
            "release-notes",
            "discussions-integration",
            "package-releases",
        ]
    }
