# functions/shared/chunker.py
import pandas as pd
import logging
import uuid
import hashlib

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Chunks CSV data into meaningful text segments for embedding.
    
    Strategies:
    1. Row-based chunking: Group N rows together
    2. Column-aware: Create natural language representations of rows
    3. Overlap: Maintain context between chunks
    """

    def __init__(
        self,
        max_chunk_size: int = 500,   # max tokens approx (chars / 4)
        rows_per_chunk: int = 10,
        overlap_rows: int = 2,
    ):
        self.max_chunk_size = max_chunk_size
        self.rows_per_chunk = rows_per_chunk
        self.overlap_rows = overlap_rows

    def chunk(
        self, 
        df: pd.DataFrame, 
        metadata: dict
    ) -> list[dict]:
        """
        Convert DataFrame rows into semantic chunks.
        
        Each chunk includes:
        - chunk_id: Unique identifier
        - chunk_text: Natural language representation
        - file_name: Source file
        - upload_id: Upload tracking ID
        - row_start: Starting row index
        - row_end: Ending row index
        - domain_tags: From metadata
        - upload_time: From metadata
        """
        chunks = []
        columns = list(df.columns)
        total_rows = len(df)
        
        # Calculate step size with overlap
        step = max(1, self.rows_per_chunk - self.overlap_rows)
        
        for start_idx in range(0, total_rows, step):
            end_idx = min(start_idx + self.rows_per_chunk, total_rows)
            chunk_df = df.iloc[start_idx:end_idx]

            # Build natural language chunk
            chunk_text = self._rows_to_text(chunk_df, columns, metadata)
            
            # Enforce max chunk size (approximate token limit)
            if len(chunk_text) > self.max_chunk_size * 4:
                # Split large chunks
                sub_chunks = self._split_large_chunk(
                    chunk_text, self.max_chunk_size * 4
                )
                for i, sub_text in enumerate(sub_chunks):
                    chunk_id = self._generate_chunk_id(
                        metadata["upload_id"], start_idx, i
                    )
                    chunks.append({
                        "chunk_id": chunk_id,
                        "chunk_text": sub_text,
                        "file_name": metadata["file_name"],
                        "upload_id": metadata["upload_id"],
                        "user_id": metadata["user_id"],
                        "row_start": start_idx,
                        "row_end": end_idx,
                        "domain_tags": metadata.get("domain_tags", []),
                        "upload_time": metadata["upload_time"],
                        "column_names": columns,
                    })
            else:
                chunk_id = self._generate_chunk_id(
                    metadata["upload_id"], start_idx, 0
                )
                chunks.append({
                    "chunk_id": chunk_id,
                    "chunk_text": chunk_text,
                    "file_name": metadata["file_name"],
                    "upload_id": metadata["upload_id"],
                    "user_id": metadata["user_id"],
                    "row_start": start_idx,
                    "row_end": end_idx,
                    "domain_tags": metadata.get("domain_tags", []),
                    "upload_time": metadata["upload_time"],
                    "column_names": columns,
                })

        logger.info(
            f"Chunked {total_rows} rows into {len(chunks)} chunks"
        )
        return chunks

    def _rows_to_text(
        self,
        chunk_df: pd.DataFrame,
        columns: list[str],
        metadata: dict,
    ) -> str:
        """Convert DataFrame rows to natural language text."""
        lines = []
        
        # Add header context
        lines.append(
            f"Data from file '{metadata['file_name']}' "
            f"(rows {chunk_df.index[0]+1}-{chunk_df.index[-1]+1} "
            f"of {metadata['row_count']}):"
        )
        lines.append(f"Columns: {', '.join(columns)}")
        lines.append("")

        # Convert each row to a readable format
        for idx, row in chunk_df.iterrows():
            row_parts = []
            for col in columns:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    # Create readable key-value pairs
                    col_display = col.replace("_", " ").title()
                    row_parts.append(f"{col_display}: {val}")
            
            if row_parts:
                lines.append(
                    f"Record {idx + 1}: {'; '.join(row_parts)}"
                )

        return "\n".join(lines)

    def _split_large_chunk(
        self, text: str, max_chars: int
    ) -> list[str]:
        """Split oversized text into smaller sub-chunks."""
        lines = text.split("\n")
        sub_chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            if current_size + len(line) > max_chars and current_chunk:
                sub_chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            current_chunk.append(line)
            current_size += len(line)

        if current_chunk:
            sub_chunks.append("\n".join(current_chunk))

        return sub_chunks

    @staticmethod
    def _generate_chunk_id(
        upload_id: str, row_start: int, sub_index: int
    ) -> str:
        """Generate deterministic chunk ID for idempotent uploads."""
        raw = f"{upload_id}:{row_start}:{sub_index}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
