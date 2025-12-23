"""Table extraction service with fallback chain."""

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from utils.table_utils import (
    remove_empty_rows_cols,
    validate_table,
    rows_to_json,
    rows_to_markdown,
    normalize_header,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    """Result of table extraction."""
    page_number: int
    rows: list[list[str]]
    title: str | None
    extraction_method: str
    confidence: float


def extract_tables_camelot_lattice(pdf_path: str, page_number: int) -> list[ExtractedTable]:
    """Extract bordered tables using Camelot lattice mode."""
    try:
        import camelot
        
        # Camelot uses 1-indexed pages
        tables = camelot.read_pdf(
            pdf_path,
            pages=str(page_number + 1),
            flavor="lattice",
        )
        
        results = []
        for table in tables:
            if table.accuracy < 50:
                continue
            
            rows = table.df.values.tolist()
            rows = remove_empty_rows_cols(rows)
            
            if validate_table(rows):
                results.append(ExtractedTable(
                    page_number=page_number,
                    rows=rows,
                    title=None,
                    extraction_method="camelot_lattice",
                    confidence=table.accuracy / 100,
                ))
        
        return results
    except Exception as e:
        logger.debug(f"Camelot lattice failed on page {page_number}: {e}")
        return []


def extract_tables_camelot_stream(pdf_path: str, page_number: int) -> list[ExtractedTable]:
    """Extract borderless tables using Camelot stream mode."""
    try:
        import camelot
        
        tables = camelot.read_pdf(
            pdf_path,
            pages=str(page_number + 1),
            flavor="stream",
        )
        
        results = []
        for table in tables:
            if table.accuracy < 40:
                continue
            
            rows = table.df.values.tolist()
            rows = remove_empty_rows_cols(rows)
            
            if validate_table(rows):
                results.append(ExtractedTable(
                    page_number=page_number,
                    rows=rows,
                    title=None,
                    extraction_method="camelot_stream",
                    confidence=table.accuracy / 100,
                ))
        
        return results
    except Exception as e:
        logger.debug(f"Camelot stream failed on page {page_number}: {e}")
        return []


def extract_tables_pdfplumber(pdf_path: str, page_number: int) -> list[ExtractedTable]:
    """Extract tables using pdfplumber alignment-based detection."""
    try:
        import pdfplumber
        
        with pdfplumber.open(pdf_path) as pdf:
            if page_number >= len(pdf.pages):
                return []
            
            page = pdf.pages[page_number]
            tables = page.extract_tables()
            
            results = []
            for table in tables:
                if not table:
                    continue
                
                rows = [[str(cell) if cell else "" for cell in row] for row in table]
                rows = remove_empty_rows_cols(rows)
                
                if validate_table(rows):
                    results.append(ExtractedTable(
                        page_number=page_number,
                        rows=rows,
                        title=None,
                        extraction_method="pdfplumber",
                        confidence=0.6,
                    ))
            
            return results
    except Exception as e:
        logger.debug(f"pdfplumber failed on page {page_number}: {e}")
        return []


def extract_tables_from_page(pdf_path: str, page_number: int) -> list[ExtractedTable]:
    """Extract tables from a page using fallback chain."""
    # Try lattice first (bordered tables)
    tables = extract_tables_camelot_lattice(pdf_path, page_number)
    if tables:
        logger.info(f"Page {page_number}: Found {len(tables)} tables via camelot_lattice")
        return tables
    
    # Try stream (borderless tables)
    tables = extract_tables_camelot_stream(pdf_path, page_number)
    if tables:
        logger.info(f"Page {page_number}: Found {len(tables)} tables via camelot_stream")
        return tables
    
    # Fallback to pdfplumber
    tables = extract_tables_pdfplumber(pdf_path, page_number)
    if tables:
        logger.info(f"Page {page_number}: Found {len(tables)} tables via pdfplumber")
        return tables
    
    return []


def process_extracted_table(table: ExtractedTable) -> dict:
    """Process extracted table into storage format."""
    table_data = rows_to_json(table.rows)
    markdown = rows_to_markdown(table.rows, table.title)
    
    return {
        "page_number": table.page_number,
        "title": table.title,
        "row_count": len(table_data["rows"]),
        "column_count": len(table_data["headers"]),
        "table_data": table_data,
        "markdown_repr": markdown,
        "extraction_method": table.extraction_method,
        "confidence": table.confidence,
    }
