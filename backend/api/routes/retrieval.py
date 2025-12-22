"""Retrieval and indexing API endpoints."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_services_ready, get_qdrant
from core.database import get_db, async_session_maker
from models.document import Document
from models.document_page import DocumentPage
from models.document_chunk import DocumentChunk
from schemas.document_chunk import (
    IndexingResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from services.chunker import chunk_document, PageText
from services.embedder import embed_chunks
from services.retriever import store_vectors, delete_document_vectors, search_similar

logger = logging.getLogger(__name__)

router = APIRouter(tags=["retrieval"])


async def index_document_task(document_id: uuid.UUID) -> int:
    """
    Background task for document indexing.
    
    Returns:
        Number of chunks created.
    """
    async with async_session_maker() as db:
        try:
            qdrant = get_qdrant()
            
            # Fetch extracted pages
            result = await db.execute(
                select(DocumentPage)
                .where(DocumentPage.document_id == document_id)
                .order_by(DocumentPage.page_number)
            )
            pages = result.scalars().all()
            
            if not pages:
                logger.warning(f"No pages found for document {document_id}")
                return 0
            
            # Convert to PageText objects
            page_texts = [
                PageText(page_number=p.page_number, text=p.extracted_text)
                for p in pages
            ]
            
            # Chunk the document
            chunks = chunk_document(page_texts)
            
            if not chunks:
                logger.warning(f"No chunks created for document {document_id}")
                return 0
            
            # Delete existing vectors FIRST (before DB changes)
            try:
                delete_document_vectors(qdrant, document_id)
            except Exception as e:
                logger.error(f"Failed to delete vectors for {document_id}: {e}")
                raise
            
            # Now delete DB chunks (vectors already gone, safe to proceed)
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            
            # Generate chunk IDs
            chunk_data = []
            for chunk in chunks:
                chunk_id = uuid.uuid4()
                chunk_data.append((chunk_id, chunk))
            
            # Generate embeddings
            embedding_input = [(cid, c.content) for cid, c in chunk_data]
            embedding_results = await embed_chunks(embedding_input)
            
            # Prepare database inserts and vector storage
            db_rows = []
            vector_points = []
            
            for (chunk_id, chunk), emb_result in zip(chunk_data, embedding_results):
                if not emb_result.success:
                    logger.warning(f"Skipping chunk {chunk.chunk_index}: {emb_result.error}")
                    continue
                
                db_rows.append({
                    "id": chunk_id,
                    "document_id": document_id,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                })
                
                vector_points.append((
                    chunk_id,
                    emb_result.embedding,
                    {
                        "chunk_id": str(chunk_id),
                        "document_id": str(document_id),
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "chunk_index": chunk.chunk_index,
                    },
                ))
            
            # Store vectors in Qdrant FIRST
            if vector_points:
                try:
                    store_vectors(qdrant, vector_points)
                except Exception as e:
                    logger.error(f"Failed to store vectors for {document_id}: {e}")
                    raise
            
            # Store in database (vectors already stored)
            if db_rows:
                stmt = insert(DocumentChunk).values(db_rows).on_conflict_do_nothing(
                    index_elements=["document_id", "chunk_index"]
                )
                await db.execute(stmt)
                await db.commit()
            
            chunks_created = len(db_rows)
            logger.info(f"Indexed document {document_id}: {chunks_created} chunks created")
            return chunks_created
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Indexing failed for document {document_id}: {e}")
            raise


@router.post(
    "/documents/{document_id}/index",
    response_model=IndexingResponse,
    dependencies=[Depends(require_services_ready)],
)
async def index_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    sync: bool = False,
) -> IndexingResponse:
    """
    Trigger chunking and embedding for a document.
    
    Set sync=true for synchronous indexing (testing).
    """
    # Validate document exists
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    # Check if pages exist
    page_count = await db.execute(
        select(func.count()).select_from(DocumentPage).where(
            DocumentPage.document_id == document_id
        )
    )
    pages = page_count.scalar() or 0
    
    if pages == 0:
        raise HTTPException(
            status_code=400,
            detail="No extracted pages found. Run text extraction first.",
        )
    
    logger.info(f"Indexing requested for document {document_id}, sync={sync}")
    
    if sync:
        # index_document_task returns chunk count after its own commit
        chunks_created = await index_document_task(document_id)
        
        return IndexingResponse(
            document_id=document_id,
            chunks_created=chunks_created,
            status="indexed",
        )
    
    # Queue background task
    background_tasks.add_task(index_document_task, document_id)
    
    return IndexingResponse(
        document_id=document_id,
        chunks_created=0,
        status="processing",
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(require_services_ready)],
)
async def search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Perform semantic search across documents."""
    qdrant = get_qdrant()
    
    # Build query preview for logging
    query_preview = request.query if len(request.query) <= 50 else request.query[:50] + "..."
    query_preview = query_preview.replace("\n", " ").replace("\r", "")
    logger.info(f"Search query: '{query_preview}', top_k={request.top_k}")
    
    # Search Qdrant
    results = await search_similar(
        qdrant,
        request.query,
        request.document_ids,
        request.top_k,
    )
    
    if not results:
        return SearchResponse(results=[], query=request.query)
    
    # Fetch chunk content from database
    chunk_ids = [r[0] for r in results]
    chunks = await db.execute(
        select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
    )
    chunk_map = {c.id: c for c in chunks.scalars().all()}
    
    # Build response
    search_results = []
    for chunk_id, score, payload in results:
        chunk = chunk_map.get(chunk_id)
        if chunk:
            search_results.append(SearchResult(
                chunk_id=chunk_id,
                document_id=chunk.document_id,
                content=chunk.content,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                score=score,
            ))
    
    logger.info(f"Search returned {len(search_results)} results")
    
    return SearchResponse(results=search_results, query=request.query)
