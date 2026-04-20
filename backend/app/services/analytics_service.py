# backend/app/services/analytics_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Computes KPIs and aggregated metrics from PostgreSQL coaching data.
    All queries are parameterized to prevent SQL injection.
    """

    def __init__(self, db_session_factory):
        """
        Args:
            db_session_factory: Callable that returns an AsyncSession
        """
        self.db_session_factory = db_session_factory

    # Mapping of KPI names to their SQL queries
    KPI_QUERIES = {
        "coaching_sessions_count": """
            SELECT COUNT(*) as total_sessions,
                   COUNT(DISTINCT DATE(period_start)) as distinct_days
            FROM coaching_analytics
            WHERE user_id = :user_id
              AND metric_name = 'coaching_session'
              AND (:region IS NULL OR region = :region)
        """,
        "avg_session_score": """
            SELECT 
                AVG(metric_value) as avg_score,
                MIN(metric_value) as min_score,
                MAX(metric_value) as max_score,
                STDDEV(metric_value) as std_dev,
                COUNT(*) as sample_size
            FROM coaching_analytics
            WHERE user_id = :user_id
              AND metric_name = 'session_score'
              AND (:region IS NULL OR region = :region)
        """,
        "completion_rate": """
            SELECT 
                COUNT(CASE WHEN metric_name = 'plan_completed' 
                      THEN 1 END)::FLOAT /
                NULLIF(COUNT(CASE WHEN metric_name = 'plan_created' 
                        THEN 1 END), 0) * 100 as completion_rate,
                COUNT(CASE WHEN metric_name = 'plan_completed' 
                      THEN 1 END) as completed,
                COUNT(CASE WHEN metric_name = 'plan_created' 
                      THEN 1 END) as total
            FROM coaching_analytics
            WHERE user_id = :user_id
              AND (:region IS NULL OR region = :region)
        """,
        "top_performers": """
            SELECT 
                dimensions->>'coach_name' as coach_name,
                dimensions->>'rep_name' as rep_name,
                AVG(metric_value) as avg_score,
                COUNT(*) as session_count
            FROM coaching_analytics
            WHERE user_id = :user_id
              AND metric_name = 'session_score'
              AND (:region IS NULL OR region = :region)
            GROUP BY dimensions->>'coach_name', 
                     dimensions->>'rep_name'
            ORDER BY avg_score DESC
            LIMIT 10
        """,
        "trend_data": """
            SELECT 
                DATE_TRUNC('week', period_start) as period,
                AVG(metric_value) as avg_value,
                COUNT(*) as data_points,
                metric_name
            FROM coaching_analytics
            WHERE user_id = :user_id
              AND period_start >= NOW() - INTERVAL '90 days'
              AND (:region IS NULL OR region = :region)
            GROUP BY DATE_TRUNC('week', period_start), metric_name
            ORDER BY period DESC
        """,
        "region_breakdown": """
            SELECT 
                region,
                AVG(metric_value) as avg_score,
                COUNT(*) as session_count,
                COUNT(DISTINCT dimensions->>'coach_name') as unique_coaches
            FROM coaching_analytics
            WHERE user_id = :user_id
              AND metric_name = 'session_score'
            GROUP BY region
            ORDER BY avg_score DESC
        """,
    }

    async def compute_kpi(
        self,
        kpi_name: str,
        user_id: str,
        region: str | None = None,
    ) -> dict:
        """
        Compute a specific KPI by name.
        
        Args:
            kpi_name: One of the predefined KPI names
            user_id: Scoped to this user's data
            region: Optional region filter
            
        Returns:
            Dict with KPI results
            
        Raises:
            ValueError: If kpi_name is not recognized
        """
        if kpi_name not in self.KPI_QUERIES:
            raise ValueError(
                f"Unknown KPI: {kpi_name}. "
                f"Available: {list(self.KPI_QUERIES.keys())}"
            )

        query = self.KPI_QUERIES[kpi_name]

        try:
            async with self.db_session_factory() as session:
                result = await session.execute(
                    text(query),
                    {"user_id": user_id, "region": region},
                )
                rows = result.mappings().all()

                # Convert to serializable dict
                data = []
                for row in rows:
                    row_dict = {}
                    for key, value in row.items():
                        if hasattr(value, "isoformat"):
                            row_dict[key] = value.isoformat()
                        elif value is None:
                            row_dict[key] = None
                        else:
                            row_dict[key] = float(value) if isinstance(
                                value, (int, float)
                            ) else str(value)
                    data.append(row_dict)

                return {
                    "kpi_name": kpi_name,
                    "user_id": user_id,
                    "region": region,
                    "results": data if len(data) > 1 else (
                        data[0] if data else {}
                    ),
                }

        except Exception as e:
            logger.error(
                f"KPI computation failed for {kpi_name}: {e}"
            )
            raise
