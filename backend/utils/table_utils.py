"""Table processing utilities."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def normalize_header(header: str) -> str:
    """Normalize table header text."""
    if not header:
        return ""
    # Remove extra whitespace, newlines
    header = re.sub(r'\s+', ' ', header.strip())
    return header


def clean_cell_value(value: Any) -> str:
    """Clean and normalize cell value."""
    if value is None:
        return ""
    val = str(value).strip()
    # Remove excessive whitespace
    val = re.sub(r'\s+', ' ', val)
    return val


def is_empty_row(row: list) -> bool:
    """Check if row is effectively empty."""
    return all(clean_cell_value(cell) == "" for cell in row)


def is_empty_column(rows: list[list], col_idx: int) -> bool:
    """Check if column is effectively empty."""
    return all(
        clean_cell_value(row[col_idx]) == "" 
        for row in rows 
        if col_idx < len(row)
    )


def remove_empty_rows_cols(rows: list[list]) -> list[list]:
    """Remove empty rows and columns from table data."""
    if not rows:
        return rows
    
    # Remove empty rows
    rows = [row for row in rows if not is_empty_row(row)]
    if not rows:
        return []
    
    # Find non-empty columns
    max_cols = max(len(row) for row in rows)
    non_empty_cols = [
        i for i in range(max_cols) 
        if not is_empty_column(rows, i)
    ]
    
    # Filter columns
    return [[row[i] if i < len(row) else "" for i in non_empty_cols] for row in rows]


def validate_table(rows: list[list], min_rows: int = 2, min_cols: int = 2) -> bool:
    """Validate table has consistent structure."""
    if not rows or len(rows) < min_rows:
        return False
    
    # Check minimum columns
    col_counts = [len(row) for row in rows]
    if max(col_counts) < min_cols:
        return False
    
    # Check column consistency (allow some variance for merged cells)
    mode_count = max(set(col_counts), key=col_counts.count)
    inconsistent = sum(1 for c in col_counts if c != mode_count)
    if inconsistent > len(rows) * 0.3:  # More than 30% inconsistent
        return False
    
    return True


def rows_to_json(rows: list[list], headers: list[str] | None = None) -> dict:
    """Convert rows to JSON structure."""
    if not rows:
        return {"headers": [], "rows": []}
    
    if headers is None:
        headers = [clean_cell_value(h) for h in rows[0]]
        data_rows = rows[1:]
    else:
        headers = [clean_cell_value(h) for h in headers]
        data_rows = rows
    
    # Normalize headers - ensure unique
    seen = {}
    unique_headers = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            unique_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            unique_headers.append(h)
    
    return {
        "headers": unique_headers,
        "rows": [[clean_cell_value(cell) for cell in row] for row in data_rows]
    }


def rows_to_markdown(rows: list[list], title: str | None = None) -> str:
    """Convert rows to markdown table."""
    if not rows:
        return ""
    
    lines = []
    if title:
        lines.append(f"**{title}**\n")
    
    # Header row
    headers = [clean_cell_value(h) for h in rows[0]]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    
    # Data rows
    for row in rows[1:]:
        cells = [clean_cell_value(cell) for cell in row]
        # Pad if needed
        while len(cells) < len(headers):
            cells.append("")
        lines.append("| " + " | ".join(cells[:len(headers)]) + " |")
    
    return "\n".join(lines)


def detect_numeric_columns(table_data: dict) -> list[int]:
    """Detect which columns contain primarily numeric data."""
    numeric_cols = []
    headers = table_data.get("headers", [])
    rows = table_data.get("rows", [])
    
    if not rows:
        return []
    
    for col_idx in range(len(headers)):
        numeric_count = 0
        total = 0
        for row in rows:
            if col_idx < len(row):
                val = row[col_idx]
                total += 1
                # Check if numeric (including currency, percentages)
                cleaned = re.sub(r'[$%,\s]', '', str(val))
                try:
                    float(cleaned)
                    numeric_count += 1
                except ValueError:
                    pass
        
        if total > 0 and numeric_count / total > 0.7:
            numeric_cols.append(col_idx)
    
    return numeric_cols
