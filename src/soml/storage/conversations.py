"""
Conversation Store - SQLite-backed conversation persistence.

Tracks:
- Conversation messages (user/assistant)
- Entities mentioned in conversation
- Entity resolution context (e.g., "dad" -> Craig Lewis's UUID)
- Conversation state (for multi-turn flows)
- Pending clarifications (questions needing user answers)

This enables:
- Multi-turn conversations with context
- Entity reference resolution ("he", "the project", "dad")
- Conversation history for LLM context
- Clarifying question flows before proposals
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4

from soml.core.config import settings, get_logger
from soml.core.types import Clarification, ClarificationPriority, ConversationState

logger = get_logger("storage.conversations")


class ConversationStore:
    """
    SQLite store for conversation state and entity context.
    
    Tables:
    - conversations: Metadata about conversations
    - messages: Individual messages in conversations
    - entity_context: Entity name -> ID mappings per conversation
    """
    
    def __init__(self, db_path: Path | None = None):
        """Initialize the conversation store."""
        self.db_path = db_path or settings.data_dir / "conversations.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            # Conversations table (extended with state and partial extraction)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT,
                    state TEXT DEFAULT 'analyzing',
                    partial_extraction TEXT
                )
            """)
            
            # Add columns if they don't exist (for migration)
            try:
                conn.execute("ALTER TABLE conversations ADD COLUMN state TEXT DEFAULT 'analyzing'")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                conn.execute("ALTER TABLE conversations ADD COLUMN partial_extraction TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    entities_mentioned TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Entity context table - maps names to entity IDs within a conversation
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entity_context (
                    conversation_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_type TEXT,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (conversation_id, name),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Pending clarifications table - tracks questions waiting for user answers
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_clarifications (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    options TEXT,
                    context TEXT,
                    default_value TEXT,
                    answer TEXT,
                    skipped INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    answered_at TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_context_conversation ON entity_context(conversation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clarifications_conversation ON pending_clarifications(conversation_id)")
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def create_conversation(self, conversation_id: str | None = None, user_id: str | None = None) -> str:
        """
        Create a new conversation.
        
        Args:
            conversation_id: Optional specific conversation ID (generates UUID if not provided)
            user_id: Optional user identifier
        
        Returns:
            Conversation ID
        """
        conv_id = conversation_id or str(uuid4())
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conv_id, user_id, now, now),
            )
            conn.commit()
        
        logger.debug(f"Created conversation: {conv_id}")
        return conv_id
    
    def get_conversation(self, conv_id: str) -> dict | None:
        """
        Get conversation metadata.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            Conversation dict or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            
            if row:
                return dict(row)
            return None
    
    def get_or_create_conversation(self, conv_id: str | None, user_id: str | None = None) -> str:
        """
        Get existing conversation or create new one.
        
        Args:
            conv_id: Conversation ID (or None for new)
            user_id: User identifier for new conversations
        
        Returns:
            Conversation ID
        """
        if conv_id:
            existing = self.get_conversation(conv_id)
            if existing:
                return conv_id
        
        return self.create_conversation(user_id)
    
    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        entities_mentioned: list[dict] | None = None,
    ) -> str:
        """
        Add a message to a conversation.
        
        Args:
            conv_id: Conversation ID
            role: "user" or "assistant"
            content: Message content
            entities_mentioned: List of {name, id, type} for entities mentioned
        
        Returns:
            Message ID
        """
        msg_id = str(uuid4())
        now = datetime.now().isoformat()
        entities_json = json.dumps(entities_mentioned) if entities_mentioned else None
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, entities_mentioned, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conv_id, role, content, entities_json, now),
            )
            
            # Update conversation timestamp
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conv_id),
            )
            
            conn.commit()
        
        logger.debug(f"Added message to conversation {conv_id}")
        return msg_id
    
    def get_messages(
        self,
        conv_id: str,
        limit: int = 50,
        before: str | None = None,
    ) -> list[dict]:
        """
        Get messages from a conversation.
        
        Args:
            conv_id: Conversation ID
            limit: Maximum messages to return
            before: Get messages before this timestamp
        
        Returns:
            List of message dicts, oldest first
        """
        with self._get_connection() as conn:
            if before:
                rows = conn.execute(
                    """
                    SELECT * FROM messages 
                    WHERE conversation_id = ? AND created_at < ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (conv_id, before, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM messages 
                    WHERE conversation_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (conv_id, limit),
                ).fetchall()
            
            messages = []
            for row in rows:
                msg = dict(row)
                if msg.get("entities_mentioned"):
                    msg["entities_mentioned"] = json.loads(msg["entities_mentioned"])
                messages.append(msg)
            
            # Return in chronological order
            messages.reverse()
            return messages
    
    def get_entity_context(self, conv_id: str) -> dict[str, str]:
        """
        Get the entity context for a conversation.
        
        Returns a dict mapping entity names to their IDs.
        This is used for resolving references like "dad" or "the project".
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            Dict of name -> entity_id
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT name, entity_id FROM entity_context WHERE conversation_id = ?",
                (conv_id,),
            ).fetchall()
            
            return {row["name"]: row["entity_id"] for row in rows}
    
    def get_entity_context_detailed(self, conv_id: str) -> list[dict]:
        """
        Get detailed entity context for a conversation.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            List of {name, entity_id, entity_type, added_at}
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM entity_context WHERE conversation_id = ?",
                (conv_id,),
            ).fetchall()
            
            return [dict(row) for row in rows]
    
    def update_entity_context(
        self,
        conv_id: str,
        name: str,
        entity_id: str,
        entity_type: str | None = None,
    ) -> None:
        """
        Add or update an entity in the conversation context.
        
        This is called after entity resolution to track what names
        refer to what entities in this conversation.
        
        Args:
            conv_id: Conversation ID
            name: The name/reference used (e.g., "dad", "Craig Lewis")
            entity_id: The resolved entity ID
            entity_type: Entity type (person, project, etc.)
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO entity_context (conversation_id, name, entity_id, entity_type, added_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conv_id, name.lower(), entity_id, entity_type, now),
            )
            conn.commit()
        
        logger.debug(f"Updated entity context in {conv_id}: {name} -> {entity_id}")
    
    def resolve_reference(
        self,
        conv_id: str,
        reference: str,
    ) -> str | None:
        """
        Try to resolve a reference using conversation context.
        
        Handles:
        - Direct name matches ("Craig Lewis")
        - Aliases ("dad", "my father")
        - Recent entity references
        
        Args:
            conv_id: Conversation ID
            reference: The reference to resolve
        
        Returns:
            Entity ID or None
        """
        context = self.get_entity_context(conv_id)
        
        # Direct match
        ref_lower = reference.lower()
        if ref_lower in context:
            return context[ref_lower]
        
        # Check if reference is contained in any context name
        for name, entity_id in context.items():
            if ref_lower in name or name in ref_lower:
                return entity_id
        
        return None
    
    def add_alias(
        self,
        conv_id: str,
        alias: str,
        entity_id: str,
    ) -> None:
        """
        Add an alias for an entity in conversation context.
        
        Useful for tracking that "dad" refers to "Craig Lewis".
        
        Args:
            conv_id: Conversation ID
            alias: The alias (e.g., "dad")
            entity_id: The entity ID it refers to
        """
        self.update_entity_context(conv_id, alias, entity_id)
    
    def clear_conversation(self, conv_id: str) -> bool:
        """
        Clear all messages and context from a conversation.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            True if conversation existed
        """
        with self._get_connection() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT id FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            
            if not existing:
                return False
            
            # Clear messages and context
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            conn.execute("DELETE FROM entity_context WHERE conversation_id = ?", (conv_id,))
            conn.commit()
        
        logger.info(f"Cleared conversation: {conv_id}")
        return True
    
    def delete_conversation(self, conv_id: str) -> bool:
        """
        Delete a conversation and all its data.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            True if conversation existed
        """
        with self._get_connection() as conn:
            # Clear related data first
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            conn.execute("DELETE FROM entity_context WHERE conversation_id = ?", (conv_id,))
            
            # Delete conversation
            cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
            
            deleted = cursor.rowcount > 0
        
        if deleted:
            logger.info(f"Deleted conversation: {conv_id}")
        return deleted
    
    def list_conversations(
        self,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        List conversations, optionally filtered by user.
        
        Args:
            user_id: Optional user filter
            limit: Maximum conversations to return
        
        Returns:
            List of conversation dicts
        """
        with self._get_connection() as conn:
            if user_id:
                rows = conn.execute(
                    """
                    SELECT * FROM conversations 
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM conversations 
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_conversation_summary(self, conv_id: str) -> dict | None:
        """
        Get a summary of a conversation.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            Dict with conversation metadata, message count, and entity count
        """
        with self._get_connection() as conn:
            conv = conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            
            if not conv:
                return None
            
            msg_count = conn.execute(
                "SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()["count"]
            
            entity_count = conn.execute(
                "SELECT COUNT(*) as count FROM entity_context WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()["count"]
            
            return {
                **dict(conv),
                "message_count": msg_count,
                "entity_count": entity_count,
            }
    
    # ============================================
    # Multi-Turn Conversation State Management
    # ============================================
    
    def set_conversation_state(
        self,
        conv_id: str,
        state: ConversationState,
        partial_extraction: dict | None = None,
    ) -> None:
        """
        Set the conversation state and optionally store partial extraction.
        
        Args:
            conv_id: Conversation ID
            state: New conversation state
            partial_extraction: Optional partial extraction data to store
        """
        now = datetime.now().isoformat()
        partial_json = json.dumps(partial_extraction) if partial_extraction else None
        
        with self._get_connection() as conn:
            if partial_extraction is not None:
                conn.execute(
                    """
                    UPDATE conversations 
                    SET state = ?, partial_extraction = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (state.value, partial_json, now, conv_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE conversations 
                    SET state = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (state.value, now, conv_id),
                )
            conn.commit()
        
        logger.debug(f"Set conversation {conv_id} state to {state.value}")
    
    def get_conversation_state(self, conv_id: str) -> tuple[ConversationState | None, dict | None]:
        """
        Get the current conversation state and partial extraction.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            Tuple of (state, partial_extraction) or (None, None) if not found
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT state, partial_extraction FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            
            if not row:
                return None, None
            
            state = ConversationState(row["state"]) if row["state"] else None
            partial = json.loads(row["partial_extraction"]) if row["partial_extraction"] else None
            
            return state, partial
    
    def get_partial_extraction(self, conv_id: str) -> dict | None:
        """
        Get the stored partial extraction for a conversation.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            Partial extraction dict or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT partial_extraction FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            
            if row and row["partial_extraction"]:
                return json.loads(row["partial_extraction"])
            return None
    
    def clear_partial_extraction(self, conv_id: str) -> None:
        """
        Clear the stored partial extraction for a conversation.
        
        Args:
            conv_id: Conversation ID
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE conversations 
                SET partial_extraction = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, conv_id),
            )
            conn.commit()
    
    # ============================================
    # Clarification Management
    # ============================================
    
    def add_clarifications(
        self,
        conv_id: str,
        clarifications: list[Clarification],
    ) -> None:
        """
        Add pending clarifications for a conversation.
        
        Args:
            conv_id: Conversation ID
            clarifications: List of Clarification objects
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            for clarification in clarifications:
                options_json = json.dumps(clarification.options) if clarification.options else None
                
                conn.execute(
                    """
                    INSERT INTO pending_clarifications 
                    (id, conversation_id, question, priority, options, context, default_value, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clarification.id,
                        conv_id,
                        clarification.question,
                        clarification.priority.value,
                        options_json,
                        clarification.context,
                        clarification.default_value,
                        now,
                    ),
                )
            
            conn.commit()
        
        logger.debug(f"Added {len(clarifications)} clarifications to conversation {conv_id}")
    
    def get_pending_clarifications(self, conv_id: str) -> list[Clarification]:
        """
        Get all pending (unanswered) clarifications for a conversation.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            List of Clarification objects
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pending_clarifications 
                WHERE conversation_id = ? AND answer IS NULL AND skipped = 0
                ORDER BY created_at ASC
                """,
                (conv_id,),
            ).fetchall()
            
            clarifications = []
            for row in rows:
                options = json.loads(row["options"]) if row["options"] else None
                clarifications.append(Clarification(
                    id=row["id"],
                    question=row["question"],
                    priority=ClarificationPriority(row["priority"]),
                    options=options,
                    context=row["context"],
                    default_value=row["default_value"],
                    answer=row["answer"],
                    skipped=bool(row["skipped"]),
                ))
            
            return clarifications
    
    def get_all_clarifications(self, conv_id: str) -> list[Clarification]:
        """
        Get all clarifications (answered and pending) for a conversation.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            List of Clarification objects
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pending_clarifications 
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conv_id,),
            ).fetchall()
            
            clarifications = []
            for row in rows:
                options = json.loads(row["options"]) if row["options"] else None
                clarifications.append(Clarification(
                    id=row["id"],
                    question=row["question"],
                    priority=ClarificationPriority(row["priority"]),
                    options=options,
                    context=row["context"],
                    default_value=row["default_value"],
                    answer=row["answer"],
                    skipped=bool(row["skipped"]),
                ))
            
            return clarifications
    
    def answer_clarification(
        self,
        conv_id: str,
        clarification_id: str,
        answer: str | None,
        skip: bool = False,
    ) -> bool:
        """
        Record an answer to a clarification question.
        
        Args:
            conv_id: Conversation ID
            clarification_id: Clarification ID
            answer: The user's answer (None if skipping)
            skip: Whether to skip this optional clarification
        
        Returns:
            True if clarification was found and updated
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE pending_clarifications 
                SET answer = ?, skipped = ?, answered_at = ?
                WHERE id = ? AND conversation_id = ?
                """,
                (answer, 1 if skip else 0, now, clarification_id, conv_id),
            )
            conn.commit()
            
            updated = cursor.rowcount > 0
        
        if updated:
            logger.debug(f"Answered clarification {clarification_id}: {answer[:50] if answer else 'skipped'}...")
        return updated
    
    def answer_all_clarifications(
        self,
        conv_id: str,
        answers: dict[str, str | None],
    ) -> int:
        """
        Record answers for multiple clarifications at once.
        
        Args:
            conv_id: Conversation ID
            answers: Dict of clarification_id -> answer (None means skipped)
        
        Returns:
            Number of clarifications updated
        """
        updated = 0
        for clarification_id, answer in answers.items():
            skip = answer is None
            if self.answer_clarification(conv_id, clarification_id, answer, skip):
                updated += 1
        return updated
    
    def has_pending_required_clarifications(self, conv_id: str) -> bool:
        """
        Check if there are any unanswered REQUIRED clarifications.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            True if there are pending required clarifications
        """
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count FROM pending_clarifications 
                WHERE conversation_id = ? 
                AND answer IS NULL 
                AND skipped = 0
                AND priority = ?
                """,
                (conv_id, ClarificationPriority.REQUIRED.value),
            ).fetchone()
            
            return row["count"] > 0
    
    def clear_clarifications(self, conv_id: str) -> int:
        """
        Clear all clarifications for a conversation.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            Number of clarifications deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM pending_clarifications WHERE conversation_id = ?",
                (conv_id,),
            )
            conn.commit()
            
            deleted = cursor.rowcount
        
        logger.debug(f"Cleared {deleted} clarifications from conversation {conv_id}")
        return deleted
    
    def get_clarification_summary(self, conv_id: str) -> dict:
        """
        Get a summary of clarifications for a conversation.
        
        Args:
            conv_id: Conversation ID
        
        Returns:
            Dict with counts: total, pending, answered, skipped, required_pending
        """
        with self._get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as count FROM pending_clarifications WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()["count"]
            
            pending = conn.execute(
                "SELECT COUNT(*) as count FROM pending_clarifications WHERE conversation_id = ? AND answer IS NULL AND skipped = 0",
                (conv_id,),
            ).fetchone()["count"]
            
            answered = conn.execute(
                "SELECT COUNT(*) as count FROM pending_clarifications WHERE conversation_id = ? AND answer IS NOT NULL",
                (conv_id,),
            ).fetchone()["count"]
            
            skipped = conn.execute(
                "SELECT COUNT(*) as count FROM pending_clarifications WHERE conversation_id = ? AND skipped = 1",
                (conv_id,),
            ).fetchone()["count"]
            
            required_pending = conn.execute(
                "SELECT COUNT(*) as count FROM pending_clarifications WHERE conversation_id = ? AND answer IS NULL AND skipped = 0 AND priority = ?",
                (conv_id, ClarificationPriority.REQUIRED.value),
            ).fetchone()["count"]
            
            return {
                "total": total,
                "pending": pending,
                "answered": answered,
                "skipped": skipped,
                "required_pending": required_pending,
            }

