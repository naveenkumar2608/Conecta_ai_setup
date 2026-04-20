# backend/app/api/v1/analytics.py
from fastapi import APIRouter, Depends, Query, HTTPException
from app.services.analytics_service import AnalyticsService
from app.dependencies import get_analytics_service, get_current_user
from app.models.api_models import UserContext
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class KPIRequest(BaseModel):
    kpi_names: list[str]
    region: str | None = None


class KPIResponse(BaseModel):
    kpis: dict
    user_id: str
    region: str | None = None


@router.get("/kpis")
async def list_available_kpis():
    """List all available KPI names and descriptions."""
    return {
        "available_kpis": [
            {
                "name": "coaching_sessions_count",
                "description": "Total coaching sessions and distinct days",
            },
            {
                "name": "avg_session_score",
                "description": "Average, min, max coaching quality score",
            },
            {
                "name": "completion_rate",
                "description": "Percentage of completed coaching plans",
            },
            {
                "name": "top_performers",
                "description": "Top 10 coaches/reps by average score",
            },
            {
                "name": "trend_data",
                "description": "Weekly trends over last 90 days",
            },
            {
                "name": "region_breakdown",
                "description": "Performance breakdown by region",
            },
        ]
    }


@router.post("/compute", response_model=KPIResponse)
async def compute_kpis(
    request: KPIRequest,
    user: UserContext = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Compute one or more KPIs directly.
    Useful for dashboards, Power BI integration, and direct API consumers.
    """
    results = {}
    errors = {}

    for kpi_name in request.kpi_names:
        try:
            result = await analytics_service.compute_kpi(
                kpi_name=kpi_name,
                user_id=user.user_id,
                region=request.region,
            )
            results[kpi_name] = result
        except ValueError as e:
            errors[kpi_name] = str(e)
        except Exception as e:
            logger.error(f"KPI computation failed for {kpi_name}: {e}")
            errors[kpi_name] = "Computation failed"

    if errors:
        results["_errors"] = errors

    return KPIResponse(
        kpis=results,
        user_id=user.user_id,
        region=request.region,
    )


@router.get("/compute/{kpi_name}")
async def compute_single_kpi(
    kpi_name: str,
    region: str | None = Query(None),
    user: UserContext = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Compute a single KPI by name."""
    try:
        result = await analytics_service.compute_kpi(
            kpi_name=kpi_name,
            user_id=user.user_id,
            region=region,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"KPI computation failed: {e}")
        raise HTTPException(status_code=500, detail="KPI computation failed")