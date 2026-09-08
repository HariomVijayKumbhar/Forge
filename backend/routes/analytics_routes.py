import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select, func, and_, or_
from pydantic import BaseModel, Field

from backend.db import engine, Run, Step, AuditLog
from backend.auth import verify_token

router = APIRouter(tags=["Analytics"])


# ==================== Models ====================

class AnalyticsSummary(BaseModel):
    total_runs: int = Field(0, description="Total number of runs")
    successful_runs: int = Field(0, description="Runs with status 'success'")
    failed_runs: int = Field(0, description="Runs with status 'error'")
    average_confidence: float = Field(0.0, description="Average confidence score")
    total_files_changed: int = Field(0, description="Total files modified across all runs")
    total_duration_hours: float = Field(0.0, description="Total execution time in hours")
    provider_distribution: Dict[str, int] = Field(default_factory=dict, description="Provider usage count")
    daily_activity: Dict[str, int] = Field(default_factory=dict, description="Runs per day")

class RunMetrics(BaseModel):
    id: str
    repo_url: str
    task: str
    status: str
    provider_used: Optional[str] = None
    confidence: Optional[int] = None
    files_changed_count: int = 0
    step_count: int = 0
    duration_seconds: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class ProviderMetrics(BaseModel):
    provider: str
    total_runs: int = 0
    success_rate: float = 0.0
    average_confidence: float = 0.0
    average_duration_seconds: float = 0.0
    average_files_changed: float = 0.0

class PerformanceMetrics(BaseModel):
    average_step_time_seconds: float = Field(0.0, description="Average time per step")
    average_iterations_per_run: float = Field(0.0, description="Average iterations per run")
    most_used_tools: Dict[str, int] = Field(default_factory=dict, description="Tool usage frequency")
    error_breakdown: Dict[str, int] = Field(default_factory=dict, description="Error types and counts")
    peak_usage_hours: Dict[str, int] = Field(default_factory=dict, description="Runs per hour of day")

class CostEstimate(BaseModel):
    provider: str
    estimated_cost_usd: float = Field(0.0, description="Estimated cost")
    estimated_tokens: int = Field(0, description="Estimated tokens used")
    runs_count: int = Field(0, description="Number of runs")

class AnalyticsFilters(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    providers: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
    min_confidence: Optional[int] = None
    max_confidence: Optional[int] = None


# ==================== Helper Functions ====================

def get_files_changed_count(run: Run) -> int:
    """Count files changed in a run"""
    if not run.files_changed:
        return 0
    try:
        files = json.loads(run.files_changed)
        return len(files) if isinstance(files, list) else 0
    except Exception:
        return2

def get_run_duration(run: Run) -> Optional[float]:
    """Calculate run duration in seconds"""
    if run.completed_at and run.created_at:
        return (run.completed_at - run.created_at).total_seconds()
    return None

def get_daily_activity(days: int = 30) -> Dict[str, int]:
    """Get daily run counts for the last N days"""
    with Session(engine) as session:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(
            func.date(Run.created_at).label("date"),
            func.count(Run.id).label("count")
        ).where(
            Run.created_at >= start_date
        ).group_by(
            func.date(Run.created_at)
        ).order_by(
            func.date(Run.created_at).desc()
        )
        
        results = session.exec(stmt).all()
        return {str(date): count for date, count in results}


# ==================== API Endpoints ====================

@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    current_user: dict = Depends(verify_token),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get comprehensive analytics summary"""
    with Session(engine) as session:
        # Basic counts
        total_runs = session.exec(select(func.count(Run.id))).first() or 0
        
        # Status distribution
        success_runs = session.exec(
            select(func.count(Run.id)).where(Run.status == "success")
        ).first() or 0
        
        failed_runs = session.exec(
            select(func.count(Run.id)).where(Run.status == "error")
        ).first() or 0
        
        # Average confidence
        avg_confidence = session.exec(
            select(func.avg(Run.confidence)).where(Run.confidence.isnot(None))
        ).first() or 0
        
        # Total files changed
        total_files = 0
        runs = session.exec(select(Run)).all()
        for run in runs:
            total_files += get_files_changed_count(run)
        
        # Provider distribution
        provider_counts = {}
        provider_stmt = select(Run.provider_used, func.count(Run.id)).group_by(Run.provider_used)
        for provider, count in session.exec(provider_stmt):
            if provider:
                provider_counts[provider] = count
        
        # Daily activity
        daily_activity = get_daily_activity(days)
        
        # Total duration
        total_duration = 0
        for run in runs:
            duration = get_run_duration(run)
            if duration:
                total_duration += duration
        
        return AnalyticsSummary(
            total_runs=total_runs,
            successful_runs=success_runs,
            failed_runs=failed_runs,
            average_confidence=float(avg_confidence) if avg_confidence else 0.0,
            total_files_changed=total_files,
            total_duration_hours=total_duration / 3600,
            provider_distribution=provider_counts,
            daily_activity=daily_activity
        )

@router.get("/analytics/runs", response_model=List[RunMetrics])
async def get_runs_with_metrics(
    current_user: dict = Depends(verify_token),
    limit: int = Query(50, ge=1, le=100, description="Number of runs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get runs with enhanced metrics"""
    with Session(engine) as session:
        runs = session.exec(
            select(Run).order_by(Run.created_at.desc()).limit(limit).offset(offset)
        ).all()
        
        metrics_list = []
        for run in runs:
            # Get step count
            step_count = session.exec(
                select(func.count(Step.id)).where(Step.run_id == run.id)
            ).first() or 0
            
            metrics_list.append(RunMetrics(
                id=run.id,
                repo_url=run.repo_url,
                task=run.task,
                status=run.status,
                provider_used=run.provider_used,
                confidence=run.confidence,
                files_changed_count=get_files_changed_count(run),
                step_count=step_count,
                duration_seconds=get_run_duration(run),
                created_at=run.created_at,
                completed_at=run.completed_at
            ))
        
        return metrics_list

@router.get("/analytics/providers", response_model=List[ProviderMetrics])
async def get_provider_metrics(
    current_user: dict = Depends(verify_token)
):
    """Get performance metrics per provider"""
    with Session(engine) as session:
        providers = session.exec(
            select(Run.provider_used).distinct().where(Run.provider_used.isnot(None))
        ).all()
        
        provider_metrics = []
        for provider in providers:
            if not provider:
                continue
                
            # Provider runs
            runs = session.exec(
                select(Run).where(Run.provider_used == provider)
            ).all()
            
            total_runs = len(runs)
            success_runs = sum(1 for r in runs if r.status == "success")
            success_rate = (success_runs / total_runs * 100) if total_runs > 0 else 0
            
            # Average confidence
            confidences = [r.confidence for r in runs if r.confidence is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Average duration
            durations = [get_run_duration(r) for r in runs]
            valid_durations = [d for d in durations if d is not None]
            avg_duration = sum(valid_durations) / len(valid_durations) if valid_durations else 0
            
            # Average files changed
            files_counts = [get_files_changed_count(r) for r in runs]
            avg_files = sum(files_counts) / len(files_counts) if files_counts else 0
            
            provider_metrics.append(ProviderMetrics(
                provider=provider,
                total_runs=total_runs,
                success_rate=success_rate,
                average_confidence=avg_confidence,
                average_duration_seconds=avg_duration,
                average_files_changed=avg_files
            ))
        
        return provider_metrics

@router.get("/analytics/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(
    current_user: dict = Depends(verify_token),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get detailed performance metrics"""
    with Session(engine) as session:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Tool usage frequency
        tool_counts = {}
        tool_stmt = select(
            Step.tool_name, func.count(Step.id)
        ).where(
            and_(
                Step.timestamp >= start_date,
                Step.tool_name.isnot(None)
            )
        ).group_by(Step.tool_name).order_by(func.count(Step.id).desc()).limit(10)
        
        for tool, count in session.exec(tool_stmt):
            if tool:
                tool_counts[tool] = count
        
        # Error breakdown
        error_counts = {}
        error_stmt = select(
            Run.error_message, func.count(Run.id)
        ).where(
            and_(
                Run.created_at >= start_date,
                Run.error_message.isnot(None)
            )
        ).group_by(Run.error_message).order_by(func.count(Run.id).desc()).limit(10)
        
        for error_msg, count in session.exec(error_stmt):
            if error_msg:
                # Truncate long error messages
                error_key = error_msg[:50] + "..." if len(error_msg) > |

@router.get("/analytics/cost-estimate", response_model=List[CostEstimate])
async def get_cost_estimates(
    current_user: dict = Depends(verify_token),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get estimated costs per provider"""
    with Session(engine) as session:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        providers = session.exec(
            select(Run.provider_used).distinct().where(
                and_(
                    Run.provider_used.isnot(None),
                    Run.created_at >= start_date
                )
            )
        ).all()
        
        estimates = []
        for provider in providers:
            if not provider:
                continue
                
            runs = session.exec(
                select(Run).where(
                    and_(
                        Run.provider_used == provider,
                        Run.created_at >= start_date
                    )
                )
            ).all()
            
            # Simple cost estimation (adjust based on provider pricing)
            estimated_cost = 0
            estimated_tokens = 0
            
            if provider == "claude":
                # Claude 3.5 Sonnet pricing: ~$3 per million input tokens
                estimated_tokens = len(runs) * 50000  # Rough estimate: 50k tokens per run
                estimated_cost = estimated_tokens / 1000000 * 3.0
            elif provider == "gemini-flash":
                # Gemini Flash pricing: ~$0.10 per million input tokens
                estimated_tokens = len(runs) *的数量 = len(runs) * 50000
                estimated_cost = estimated_tokens / 1000000 * 0.1
            elif provider == "openrouter":
                # OpenRouter pricing varies, use average
                estimated_tokens = len(runs) * 50000
                estimated_cost = estimated_tokens / 1000000 * 1.5
            elif provider == "groq":
                # Groq Mixtral pricing: free tier
                estimated_cost = 0
                estimated_tokens = len(runs) * 50000
            else:
                estimated_tokens = len(runs) * 50000
                estimated_cost = estimated_tokens / 1000000 * 2.0  # Default
            
            estimates.append(CostEstimate(
                provider=provider,
                estimated_cost_usd=round(estimated_cost, 4),
                estimated_tokens=estimated_tokens,
                runs_count=len(runs)
            ))
        
        return estimates

@router.get("/analytics/export")
async def export_analytics_data(
    current_user: dict = Depends(verify_token),
    format: str = Query("json", enum=["json", "csv"])
):
    """Export analytics data in various formats"""
    with Session(engine) as session:
        runs = session.exec(select(Run)).all()
        steps = session.exec(select(Step)).all()
        
        if format == "csv":
            # Create CSV data
            csv_lines = ["id,repo_url,task,status,provider_used,confidence,created_at,completed_at"]
            for run in runs:
                csv_lines.append(
                    f"{run.id},{run.repo_url},{run.task},{run.status},{run.provider_used or ''},"
                    f"{run.confidence or ''},{run.created_at},{run.completed_at or ''}"
                )
            return {"data": "\n".join(csv_lines), "format": "csv"}
        else:
            # JSON format
            return {
                "runs": [run.dict() for run in runs],
                "steps": [step.dict() for step in steps],
                "format": "json"
            }
