import pandas as pd
import io
import logging
import chardet

logger = logging.getLogger(__name__)


class CSVParser:
    """
    Robust CSV parser with encoding detection,
    normalization, and validation.
    """

    SUPPORTED_ENCODINGS = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
    MAX_ROWS = 100_000
    
    def parse(
        self, 
        raw_data: bytes, 
        file_name: str
    ) -> pd.DataFrame:
        """
        Parse raw CSV bytes into a normalized DataFrame.
        
        Steps:
        1. Detect encoding
        2. Read CSV with pandas
        3. Normalize column names
        4. Clean data (strip whitespace, handle nulls)
        5. Validate row count
        """
        # Step 1: Detect encoding
        detected = chardet.detect(raw_data[:10000])
        encoding = detected.get("encoding", "utf-8")
        confidence = detected.get("confidence", 0)
        logger.info(
            f"Detected encoding: {encoding} "
            f"(confidence: {confidence:.2f})"
        )

        # Step 2: Read CSV
        try:
            df = pd.read_csv(
                io.BytesIO(raw_data),
                encoding=encoding,
                low_memory=False,
                na_values=["", "N/A", "null", "NULL", "None"],
                skipinitialspace=True,
            )
        except UnicodeDecodeError:
            # Fallback encodings
            for fallback_enc in self.SUPPORTED_ENCODINGS:
                try:
                    df = pd.read_csv(
                        io.BytesIO(raw_data),
                        encoding=fallback_enc,
                        low_memory=False,
                    )
                    logger.info(
                        f"Fallback encoding succeeded: {fallback_enc}"
                    )
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(
                    f"Cannot decode CSV file {file_name} "
                    f"with any supported encoding"
                )

        # Step 3: Normalize column names
        df.columns = [
            col.strip()
               .lower()
               .replace(" ", "_")
               .replace("-", "_")
               .replace(".", "_")
            for col in df.columns
        ]

        # Step 4: Clean data
        # Strip whitespace from string columns
        str_cols = df.select_dtypes(include=["object"]).columns
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({"nan": None, "": None})

        # Drop completely empty rows
        df = df.dropna(how="all").reset_index(drop=True)

        # Step 5: Validate
        if len(df) > self.MAX_ROWS:
            logger.warning(
                f"CSV has {len(df)} rows, truncating to {self.MAX_ROWS}"
            )
            df = df.head(self.MAX_ROWS)

        if len(df) == 0:
            raise ValueError(f"CSV file {file_name} contains no data rows")

        logger.info(
            f"Parsed CSV: {len(df)} rows × {len(df.columns)} columns"
        )
        return df
