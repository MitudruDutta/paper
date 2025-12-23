"""Conversation manager for follow-up question handling."""

import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.qa_conversation import QAConversation
from models.qa_message import QAMessage

logger = logging.getLogger(__name__)

# Coreference patterns
COREFERENCE_PATTERNS = [
    (r'\b(it|this|that|these|those)\b', 'demonstrative'),
    (r'\b(the same|the above|the previous|the latter|the former)\b', 'reference'),
    (r'\b(compare|comparison|versus|vs\.?|differ|difference)\b', 'comparison'),
    (r'\bhow does (it|that|this)\b', 'follow_up'),
    (r'\bwhat about\b', 'follow_up'),
    (r'\band (the|that|those)\b', 'continuation'),
]


@dataclass
class ConversationContext:
    """Extracted context from conversation history."""
    entities: list[str]
    last_question: str | None
    last_answer: str | None
    rewritten_question: str
    needs_rewrite: bool


def extract_entities(text: str) -> list[str]:
    """Extract key entities from text using patterns."""
    entities = []
    
    # Numbers with context (Q1, Q2, 2023, $100M, 15%)
    entities.extend(re.findall(r'Q[1-4]', text, re.IGNORECASE))
    entities.extend(re.findall(r'\b20\d{2}\b', text))
    entities.extend(re.findall(r'\$[\d.]+[BMK]?\b', text, re.IGNORECASE))
    entities.extend(re.findall(r'\b\d+(?:\.\d+)?%', text))
    
    # Capitalized terms (likely proper nouns/concepts)
    entities.extend(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text))
    
    # Common business terms
    business_terms = re.findall(
        r'\b(revenue|profit|margin|growth|sales|cost|expense|income|earnings|EBITDA)\b',
        text, re.IGNORECASE
    )
    entities.extend([t.lower() for t in business_terms])
    
    return list(set(entities))


def needs_coreference_resolution(question: str) -> bool:
    """Check if question contains unresolved references."""
    question_lower = question.lower()
    for pattern, _ in COREFERENCE_PATTERNS:
        if re.search(pattern, question_lower):
            return True
    return False


def rewrite_with_context(question: str, last_question: str, last_answer: str, entities: list[str]) -> str:
    """Rewrite question by resolving coreferences using rule-based approach."""
    rewritten = question
    
    # Build entity context string
    entity_context = ", ".join(entities[:5]) if entities else ""
    
    # Replace demonstratives with entity context
    if entity_context:
        # "it" -> specific entity if only one main entity
        if re.search(r'\bit\b', rewritten, re.IGNORECASE) and len(entities) == 1:
            rewritten = re.sub(r'\bit\b', entities[0], rewritten, flags=re.IGNORECASE)
        
        # "that/this" with context
        if re.search(r'\b(that|this)\b', rewritten, re.IGNORECASE):
            # Try to find the subject from last question
            subject_match = re.search(r'(?:what|how|when|where|why|which)\s+(?:is|was|are|were|did)?\s*(?:the\s+)?(\w+(?:\s+\w+)?)', 
                                     last_question, re.IGNORECASE)
            if subject_match:
                subject = subject_match.group(1)
                rewritten = re.sub(r'\b(that|this)\b', subject, rewritten, count=1, flags=re.IGNORECASE)
    
    # Handle comparison follow-ups
    if re.search(r'\bhow does (it|that|this) compare\b', rewritten, re.IGNORECASE):
        # Extract what was being discussed
        if entities:
            main_entity = entities[0]
            rewritten = re.sub(
                r'\bhow does (it|that|this) compare\b',
                f'how does {main_entity} compare',
                rewritten,
                flags=re.IGNORECASE
            )
    
    # "what about X" -> "what is X" with context
    if re.search(r'\bwhat about\b', rewritten, re.IGNORECASE):
        # Keep the rest but add context
        rewritten = re.sub(r'\bwhat about\b', 'what is', rewritten, flags=re.IGNORECASE)
        if entity_context and entity_context not in rewritten:
            rewritten = f"{rewritten} (in context of {entity_context})"
    
    return rewritten


async def get_or_create_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID | None,
) -> tuple[QAConversation, bool]:
    """Get existing conversation or create new one."""
    if conversation_id:
        result = await db.execute(
            select(QAConversation)
            .options(selectinload(QAConversation.messages))
            .where(QAConversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            logger.info(f"Retrieved conversation {conversation_id} with {len(conversation.messages)} messages")
            return conversation, False
        logger.warning(f"Conversation {conversation_id} not found, creating new")
    
    conversation = QAConversation()
    conversation.messages = []  # Initialize empty list to avoid lazy load
    db.add(conversation)
    await db.flush()
    logger.info(f"Created new conversation {conversation.id}")
    return conversation, True


async def resolve_followup(
    question: str,
    conversation: QAConversation,
) -> ConversationContext:
    """Resolve coreferences in follow-up question."""
    messages = conversation.messages
    
    # No history - return as-is
    if not messages:
        return ConversationContext(
            entities=[],
            last_question=None,
            last_answer=None,
            rewritten_question=question,
            needs_rewrite=False,
        )
    
    # Get last exchange
    last_user = None
    last_assistant = None
    for msg in reversed(messages):
        if msg.role == "assistant" and last_assistant is None:
            last_assistant = msg.content
        elif msg.role == "user" and last_user is None:
            last_user = msg.content
        if last_user and last_assistant:
            break
    
    # Check if resolution needed
    if not needs_coreference_resolution(question):
        return ConversationContext(
            entities=extract_entities(last_assistant or ""),
            last_question=last_user,
            last_answer=last_assistant,
            rewritten_question=question,
            needs_rewrite=False,
        )
    
    # Extract entities from last exchange
    entities = []
    if last_user:
        entities.extend(extract_entities(last_user))
    if last_assistant:
        entities.extend(extract_entities(last_assistant))
    entities = list(set(entities))
    
    # Rewrite question
    rewritten = question
    if last_user and last_assistant:
        rewritten = rewrite_with_context(question, last_user, last_assistant, entities)
    
    logger.info(f"Resolved follow-up: '{question}' -> '{rewritten}'")
    
    return ConversationContext(
        entities=entities,
        last_question=last_user,
        last_answer=last_assistant,
        rewritten_question=rewritten,
        needs_rewrite=rewritten != question,
    )


async def add_message(
    db: AsyncSession,
    conversation: QAConversation,
    role: str,
    content: str,
    cited_pages: list[int] | None = None,
    document_ids: list[uuid.UUID] | None = None,
) -> QAMessage:
    """Add a message to the conversation."""
    message = QAMessage(
        conversation_id=conversation.id,
        role=role,
        content=content,
        cited_pages=cited_pages,
        document_ids=document_ids,
    )
    db.add(message)
    await db.flush()
    return message
