"""Prompt construction for RAG question answering."""

import uuid
from dataclasses import dataclass


@dataclass
class ChunkContext:
    """A chunk with its metadata for context assembly."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    page_start: int
    page_end: int


SYSTEM_PROMPT = """You are a document analysis assistant. Answer questions using ONLY the provided context.

STRICT RULES:
1. Use ONLY information from the context below
2. Cite every fact with [Page X] or [Pages X-Y] format
3. ONLY use page numbers from the "VALID PAGES" list
4. If information is not in context, respond EXACTLY: "I cannot find this information in the provided document."
5. Never invent or guess page numbers
6. Never use external knowledge

RESPONSE FORMAT:
- Short, direct answers
- Every sentence must end with a citation
- Example: "The system uses three components [Page 5]. These include X, Y, and Z [Pages 7-8]."
"""


def assemble_context(chunks: list[ChunkContext]) -> tuple[str, list[int]]:
    """
    Assemble chunks into formatted context string.
    
    Returns:
        Tuple of (context_string, list of valid pages)
    """
    context_parts = []
    all_pages = set()
    
    for chunk in chunks:
        for p in range(chunk.page_start, chunk.page_end + 1):
            all_pages.add(p)
        
        if chunk.page_start == chunk.page_end:
            page_info = f"Page {chunk.page_start}"
        else:
            page_info = f"Pages {chunk.page_start}-{chunk.page_end}"
        
        context_parts.append(f"--- {page_info} ---\n{chunk.content}")
    
    return "\n\n".join(context_parts), sorted(all_pages)


def build_user_prompt(context: str, question: str, valid_pages: list[int]) -> str:
    """Build the user prompt with context and question."""
    return f"""CONTEXT:
{context}

VALID PAGES: {valid_pages}
(You may ONLY cite these page numbers)

QUESTION: {question}

ANSWER:"""


def build_messages(chunks: list[ChunkContext], question: str) -> tuple[list[dict], list[int]]:
    """Build complete message list for LLM. Returns messages and valid pages."""
    context, valid_pages = assemble_context(chunks)
    user_prompt = build_user_prompt(context, question, valid_pages)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    return messages, valid_pages
