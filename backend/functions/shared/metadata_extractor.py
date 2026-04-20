# functions/shared/metadata_extractor.py
import pandas as pd
from datetime import datetime, timezone
import logging
import re

logger = logging.getLogger(__name__)


# Domain tag mapping — matches column names to coaching domains
DOMAIN_TAG_PATTERNS = {
    "coaching": [
        r"coach", r"session", r"feedback", r"mentor"
    ],
    "performance": [
        r"score", r"rating", r"performance", r"kpi", r"metric"
    ],
    "sales": [
        r"sale", r"revenue", r"pipeline", r"quota", r"target"
    ],
    "training": [
        r"training", r"completion", r"certification", r"module"
    ],
    "medical_device": [
        r"device", r"product", r"libre", r"sensor", r"cgm"
    ],
    "field_activity": [
        r"visit", r"call", r"territory", r"region", r"hcp"
    ],
}


class MetadataExtractor:
    """Extracts structured metadata from parsed CSV DataFrames."""

    def extract(
        self,
        df: pd.DataFrame,
        file_name: str,
        upload_id: str,
        user_id: str,
    ) -> dict:
        """
        Extract metadata:
        - file_name
        - upload_time
        - column_names
        - row_count
        - domain_tags (auto-detected from column names and content)
        - column_types
        - sample_values
        """
        column_names = list(df.columns)
        column_types = {
            col: str(dtype) for col, dtype in df.dtypes.items()
        }
        
        # Auto-detect domain tags
        domain_tags = self._detect_domain_tags(column_names, df)
        
        # Sample values (first non-null value per column, for reference)
        sample_values = {}
        for col in column_names[:20]:  # Limit to first 20 columns
            non_null = df[col].dropna()
            if len(non_null) > 0:
                sample_values[col] = str(non_null.iloc[0])[:100]

        metadata = {
            "upload_id": upload_id,
            "user_id": user_id,
            "file_name": file_name,
            "upload_time": datetime.now(timezone.utc).isoformat(),
            "column_names": column_names,
            "column_types": column_types,
            "row_count": len(df),
            "column_count": len(column_names),
            "domain_tags": domain_tags,
            "sample_values": sample_values,
            "null_percentages": {
                col: round(df[col].isna().mean() * 100, 2) 
                for col in column_names
            },
        }

        logger.info(
            f"Extracted metadata: {len(column_names)} columns, "
            f"{len(df)} rows, tags={domain_tags}"
        )
        return metadata

    def _detect_domain_tags(
        self, 
        column_names: list[str], 
        df: pd.DataFrame
    ) -> list[str]:
        """Auto-detect domain tags based on column names and content."""
        detected_tags = set()
        all_text = " ".join(column_names).lower()
        
        # Check column names against patterns
        for domain, patterns in DOMAIN_TAG_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, all_text):
                    detected_tags.add(domain)
                    break

        # Also check first few string values for domain hints
        str_cols = df.select_dtypes(include=["object"]).columns[:5]
        for col in str_cols:
            sample_text = " ".join(
                df[col].dropna().head(10).astype(str)
            ).lower()
            for domain, patterns in DOMAIN_TAG_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, sample_text):
                        detected_tags.add(domain)
                        break

        return list(detected_tags) if detected_tags else ["general"]
