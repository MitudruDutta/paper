"""Table-based QA service."""

import logging
import os
import re
import uuid
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

STOPWORDS = {"the", "a", "an", "is", "was", "are", "were", "what", "how", "of", "in", "for", "to", "and", "or", "it", "this", "that"}


def _get_numeric_coerce_threshold() -> float:
    """Get numeric coercion threshold from env with validation."""
    default = 0.8
    env_val = os.getenv("TABLE_QA_NUMERIC_COERCE_THRESHOLD")
    if env_val is None:
        return default
    try:
        val = float(env_val)
        if not 0.0 <= val <= 1.0:
            logger.warning(f"TABLE_QA_NUMERIC_COERCE_THRESHOLD={val} out of range [0,1], using {default}")
            return default
        return val
    except ValueError:
        logger.warning(f"Invalid TABLE_QA_NUMERIC_COERCE_THRESHOLD='{env_val}', using {default}")
        return default


NUMERIC_COERCE_THRESHOLD = _get_numeric_coerce_threshold()


@dataclass
class TableQueryResult:
    """Result of a table query."""
    answer: str
    table_id: uuid.UUID
    page_number: int
    computation_performed: str | None
    success: bool
    error: str | None = None
    row_data: dict = field(default_factory=dict)


def table_to_dataframe(table_data: dict, numeric_threshold: float | None = None) -> pd.DataFrame | None:
    """Convert table JSON to pandas DataFrame.
    
    Args:
        table_data: Dict with 'headers' and 'rows' keys
        numeric_threshold: Override for NUMERIC_COERCE_THRESHOLD (0.0-1.0)
    
    Raises:
        TypeError: If numeric_threshold is not a number
        ValueError: If numeric_threshold is outside [0.0, 1.0]
    """
    if numeric_threshold is not None:
        if not isinstance(numeric_threshold, (int, float)):
            raise TypeError(f"numeric_threshold must be a number, got {type(numeric_threshold).__name__}")
        if not 0.0 <= numeric_threshold <= 1.0:
            raise ValueError(f"numeric_threshold must be in [0.0, 1.0], got {numeric_threshold}")
    threshold = numeric_threshold if numeric_threshold is not None else NUMERIC_COERCE_THRESHOLD
    
    try:
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        
        if not headers or not rows:
            return None
        
        df = pd.DataFrame(rows, columns=headers)
        
        for col in df.columns:
            try:
                cleaned = df[col].astype(str).str.replace(r'[$,€£%\s]', '', regex=True)
                coerced = pd.to_numeric(cleaned, errors='coerce')
                # Replace column with numeric dtype (NaNs for failed conversions) only if success rate >= threshold
                if coerced.notna().mean() >= threshold:
                    df[col] = coerced
                else:
                    logger.debug(f"Column '{col}' skipped numeric conversion (success rate below threshold)")
            except Exception as e:
                logger.debug(f"Column '{col}' conversion error: {e}")
        
        return df
    except Exception as e:
        logger.error(f"Failed to create DataFrame: {e}")
        return None


def _extract_keywords(text: str) -> list[str]:
    """Extract content words, filtering stopwords."""
    words = re.findall(r'\b(\w+)\b', text)
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def detect_table_query_intent(question: str) -> tuple[str, list[str]]:
    """Detect what kind of table operation is being requested."""
    question_lower = question.lower()
    keywords = _extract_keywords(question_lower)
    
    if any(word in question_lower for word in ["average", "mean", "avg"]):
        return "average", keywords
    if any(word in question_lower for word in ["sum", "total"]):
        return "sum", keywords
    if any(word in question_lower for word in ["maximum", "max", "highest", "largest"]):
        return "max", keywords
    if any(word in question_lower for word in ["minimum", "min", "lowest", "smallest"]):
        return "min", keywords
    if any(word in question_lower for word in ["count", "how many"]):
        return "count", keywords
    if any(word in question_lower for word in ["compare", "difference", "vs", "versus"]):
        return "compare", keywords
    if any(word in question_lower for word in ["what is", "what was", "find", "show"]):
        return "lookup", keywords
    
    # General intent still gets keywords for potential column matching
    return "general", keywords


def find_matching_column(df: pd.DataFrame | None, keywords: list[str]) -> str | None:
    """Find column that best matches keywords using word-boundary matching."""
    if df is None:
        return None
    
    for col in df.columns:
        col_lower = col.lower()
        for keyword in keywords:
            # Use word boundary regex to avoid false positives like "id" matching "valid"
            if re.search(rf'\b{re.escape(keyword)}\b', col_lower):
                return col
    return None


def execute_table_query(
    table_id: uuid.UUID,
    table_data: dict,
    page_number: int,
    question: str,
    numeric_threshold: float | None = None,
) -> TableQueryResult:
    """Execute a query against table data.
    
    Args:
        numeric_threshold: Override for numeric coercion threshold (0.0-1.0), defaults to NUMERIC_COERCE_THRESHOLD
    """
    df = table_to_dataframe(table_data, numeric_threshold=numeric_threshold)
    if df is None:
        return TableQueryResult(
            answer="Unable to process table data",
            table_id=table_id,
            page_number=page_number,
            computation_performed=None,
            success=False,
            error="Failed to parse table",
        )
    
    intent, keywords = detect_table_query_intent(question)
    target_col = find_matching_column(df, keywords)
    
    try:
        if intent == "average" and target_col:
            if pd.api.types.is_numeric_dtype(df[target_col]):
                result = df[target_col].mean()
                return TableQueryResult(
                    answer=f"The average {target_col} is {result:.2f}",
                    table_id=table_id,
                    page_number=page_number,
                    computation_performed=f"mean({target_col})",
                    success=True,
                )
            else:
                return TableQueryResult(
                    answer=f"Cannot compute average: column '{target_col}' is not numeric",
                    table_id=table_id,
                    page_number=page_number,
                    computation_performed=f"mean({target_col})",
                    success=False,
                    error="non_numeric_column",
                )
        
        elif intent == "sum" and target_col:
            if pd.api.types.is_numeric_dtype(df[target_col]):
                result = df[target_col].sum()
                return TableQueryResult(
                    answer=f"The total {target_col} is {result:.2f}",
                    table_id=table_id,
                    page_number=page_number,
                    computation_performed=f"sum({target_col})",
                    success=True,
                )
            else:
                return TableQueryResult(
                    answer=f"Cannot compute sum: column '{target_col}' is not numeric",
                    table_id=table_id,
                    page_number=page_number,
                    computation_performed=f"sum({target_col})",
                    success=False,
                    error="non_numeric_column",
                )
        
        elif intent == "max" and target_col:
            if pd.api.types.is_numeric_dtype(df[target_col]):
                result = df[target_col].max()
                idx = df[target_col].idxmax()
                row_data = df.iloc[idx].to_dict() if pd.notna(idx) else {}
                return TableQueryResult(
                    answer=f"The maximum {target_col} is {result:.2f}",
                    table_id=table_id,
                    page_number=page_number,
                    computation_performed=f"max({target_col})",
                    success=True,
                    row_data=row_data,
                )
            else:
                return TableQueryResult(
                    answer=f"Cannot compute maximum: column '{target_col}' is not numeric",
                    table_id=table_id,
                    page_number=page_number,
                    computation_performed=f"max({target_col})",
                    success=False,
                    error="non_numeric_column",
                )
        
        elif intent == "min" and target_col:
            if pd.api.types.is_numeric_dtype(df[target_col]):
                result = df[target_col].min()
                idx = df[target_col].idxmin()
                row_data = df.iloc[idx].to_dict() if pd.notna(idx) else {}
                return TableQueryResult(
                    answer=f"The minimum {target_col} is {result:.2f}",
                    table_id=table_id,
                    page_number=page_number,
                    computation_performed=f"min({target_col})",
                    success=True,
                    row_data=row_data,
                )
            else:
                return TableQueryResult(
                    answer=f"Cannot compute minimum: column '{target_col}' is not numeric",
                    table_id=table_id,
                    page_number=page_number,
                    computation_performed=f"min({target_col})",
                    success=False,
                    error="non_numeric_column",
                )
        
        elif intent == "count":
            result = len(df)
            return TableQueryResult(
                answer=f"The table contains {result} rows",
                table_id=table_id,
                page_number=page_number,
                computation_performed="count(rows)",
                success=True,
            )
        
        return TableQueryResult(
            answer=f"Table has {len(df)} rows and {len(df.columns)} columns: {', '.join(df.columns)}",
            table_id=table_id,
            page_number=page_number,
            computation_performed=None,
            success=True,
        )
        
    except Exception as e:
        logger.error(f"Table query failed: {e}")
        return TableQueryResult(
            answer="Unable to compute result from table",
            table_id=table_id,
            page_number=page_number,
            computation_performed=None,
            success=False,
            error=str(e),
        )
