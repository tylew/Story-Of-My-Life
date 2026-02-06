"""
Neo4j Graph Store - Graph relationships and vector embeddings.

Neo4j serves as a queryable cache for:
- Entity nodes with properties
- Relationship edges between entities
- Vector embeddings for semantic search

This is a DERIVED cache - if Neo4j is lost, it can be rebuilt from markdown.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator
from uuid import UUID

from neo4j import GraphDatabase, Driver, ManagedTransaction

from soml.core.config import settings, get_logger
from soml.core.types import (
    Entity,
    EntityType,
    Event,
    Goal,
    Memory,
    Note,
    Person,
    Project,
    Relationship,
    RelationshipCategory,
)

logger = get_logger("storage.graph")


class GraphStore:
    """
    Neo4j graph store for relationships and vector search.
    
    Node labels correspond to entity types:
    - :Person
    - :Project
    - :Goal
    - :Event
    - :Note
    - :Memory
    - :Entity (base label for all)
    
    Relationship types:
    - :RELATES_TO (general with 'type' property)
    - :KNOWS (person to person)
    - :WORKS_ON (person to project)
    - :PART_OF (hierarchical)
    """
    
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        """Initialize the graph store."""
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self._driver: Driver | None = None
    
    @property
    def driver(self) -> Driver:
        """Lazy initialization of the Neo4j driver."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
        return self._driver
    
    def close(self) -> None:
        """Close the driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
    
    @contextmanager
    def session(self):
        """Get a database session."""
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def ensure_indexes(self) -> None:
        """
        Ensure necessary indexes exist, including the vector index for embeddings.
        
        Should be called on application startup.
        """
        with self.session() as session:
            # Create unique constraint on Entity.id
            try:
                session.run("""
                    CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                    FOR (e:Entity) REQUIRE e.id IS UNIQUE
                """)
                logger.info("Created entity ID unique constraint")
            except Exception as e:
                logger.debug(f"Entity ID constraint may already exist: {e}")
            
            # Create vector index for embeddings
            # Neo4j 5.x syntax for vector index
            try:
                session.run(f"""
                    CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS
                    FOR (e:Entity)
                    ON e.embedding
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: {settings.embedding_dimensions},
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                """)
                logger.info(f"Created vector index 'entity_embeddings' with {settings.embedding_dimensions} dimensions")
            except Exception as e:
                logger.debug(f"Vector index may already exist or Neo4j version doesn't support it: {e}")
            
            # Create full-text index for entity search
            try:
                session.run("""
                    CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
                    FOR (e:Entity)
                    ON EACH [e.name, e.title, e.description, e.disambiguator]
                """)
                logger.info("Created fulltext index 'entity_fulltext'")
            except Exception as e:
                logger.debug(f"Fulltext index may already exist: {e}")
    
    def _entity_to_node_props(self, entity: Entity) -> dict[str, Any]:
        """Convert an entity to Neo4j node properties."""
        props = {
            "id": str(entity.id),
            "entity_type": entity.entity_type,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
            "source": entity.source.value if hasattr(entity.source, 'value') else entity.source,
            "needs_review": entity.needs_review,
            "review_reason": entity.review_reason,
            "tags": entity.tags,
        }
        
        # Type-specific properties
        if isinstance(entity, Person):
            props.update({
                "name": entity.name,
                "disambiguator": entity.disambiguator,
                "last_interaction": entity.last_interaction.isoformat() if entity.last_interaction else None,
            })
        elif isinstance(entity, Project):
            props.update({
                "name": entity.name,
                "description": entity.description,
                "status": entity.status,
                "last_activity": entity.last_activity.isoformat() if entity.last_activity else None,
            })
        elif isinstance(entity, Goal):
            props.update({
                "title": entity.title,
                "description": entity.description,
                "status": entity.status,
                "progress": entity.progress,
            })
        elif isinstance(entity, Event):
            props.update({
                "title": entity.title,
                "description": entity.description,
                "temporal_state": entity.temporal_state.value if hasattr(entity.temporal_state, 'value') else entity.temporal_state,
                "start_time": entity.start_time.isoformat() if entity.start_time else None,
            })
        elif isinstance(entity, Note):
            props.update({
                "title": entity.title,
                "content": entity.content[:500] if entity.content else None,  # Truncate for graph
                "temporal_state": entity.temporal_state.value if hasattr(entity.temporal_state, 'value') else entity.temporal_state,
            })
        elif isinstance(entity, Memory):
            props.update({
                "title": entity.title,
                "summary": entity.summary[:500] if entity.summary else None,
                "themes": entity.themes,
            })
        
        return props
    
    def _get_label(self, entity_type: EntityType | str) -> str:
        """Get the Neo4j label for an entity type."""
        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
        return type_str.capitalize()
    
    def upsert_node(self, entity: Entity) -> None:
        """
        Create or update a node for an entity.
        
        Uses MERGE to ensure idempotent operations.
        """
        label = self._get_label(entity.entity_type)
        props = self._entity_to_node_props(entity)
        
        with self.session() as session:
            session.run(
                f"""
                MERGE (e:Entity:{label} {{id: $id}})
                SET e += $props
                """,
                id=str(entity.id),
                props=props,
            )
            logger.debug(f"Upserted node {entity.id} with label {label}")
    
    def get_node(self, entity_id: str | UUID) -> dict[str, Any] | None:
        """Get a node by ID."""
        with self.session() as session:
            result = session.run(
                "MATCH (e:Entity {id: $id}) RETURN e",
                id=str(entity_id),
            )
            record = result.single()
            if record:
                return dict(record["e"])
            return None
    
    def delete_node(self, entity_id: str | UUID) -> bool:
        """Delete a node and all its relationships."""
        with self.session() as session:
            result = session.run(
                "MATCH (e:Entity {id: $id}) DETACH DELETE e RETURN count(e) as deleted",
                id=str(entity_id),
            )
            record = result.single()
            return record["deleted"] > 0 if record else False
    
    def update_node(self, entity_id: str | UUID, updates: dict[str, Any]) -> bool:
        """
        Update properties on an existing node.
        
        Args:
            entity_id: The entity ID
            updates: Dictionary of properties to update
        
        Returns:
            True if the node was found and updated, False otherwise.
        """
        if not updates:
            return True  # Nothing to update
        
        # Clean up updates - convert complex types to strings
        clean_updates = {}
        for key, value in updates.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                clean_updates[key] = value
            elif isinstance(value, dict):
                # Store dicts as JSON strings in Neo4j
                import json
                clean_updates[key] = json.dumps(value)
            elif isinstance(value, list):
                # Keep simple lists, JSON encode complex ones
                if all(isinstance(v, (str, int, float, bool)) for v in value):
                    clean_updates[key] = value
                else:
                    import json
                    clean_updates[key] = json.dumps(value)
            else:
                clean_updates[key] = str(value)
        
        # Add updated_at
        clean_updates["updated_at"] = datetime.now().isoformat()
        
        with self.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {id: $id})
                SET e += $props
                RETURN count(e) as updated
                """,
                id=str(entity_id),
                props=clean_updates,
            )
            record = result.single()
            updated = record["updated"] > 0 if record else False
            
            if updated:
                logger.debug(f"Updated node {entity_id} with {list(clean_updates.keys())}")
            
            return updated
    
    def create_relationship(
        self,
        source_id: str | UUID,
        target_id: str | UUID,
        relationship_type: str,
        category: RelationshipCategory | str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a relationship between two entities.
        
        Always creates a new relationship with a unique ID. Multiple relationships
        of the same type between the same entities are allowed (for different contexts,
        time periods, projects, etc.).
        
        Uses :RELATES_TO as the base relationship with type and rich data as properties.
        
        Args:
            source_id: Source entity UUID
            target_id: Target entity UUID
            relationship_type: Type of relationship (e.g., 'friend', 'works_with')
            category: Personal or structural
            properties: Rich relationship data including:
                - id: Unique relationship ID (auto-generated if not provided)
                - strength: 0.0-1.0 relationship strength
                - sentiment: -1.0 to 1.0 emotional sentiment
                - confidence: 0.0-1.0 confidence level
                - context: Why/how this relationship exists
                - notes: Additional notes
                - started_at: When relationship started
                - ended_at: When relationship ended
                - source: How created ('user', 'agent', 'import')
                - source_text: Original text that created this
        
        Returns:
            The unique relationship ID
        """
        from uuid import uuid4 as gen_uuid
        
        cat_str = category.value if isinstance(category, RelationshipCategory) else category
        props = properties or {}
        
        # Core fields
        props["type"] = relationship_type
        props["category"] = cat_str
        props["created_at"] = datetime.now().isoformat()
        props["updated_at"] = datetime.now().isoformat()
        
        # Ensure unique ID
        if "id" not in props:
            props["id"] = str(gen_uuid())
        rel_id = props["id"]
        
        # Default rich data fields
        props.setdefault("strength", 0.5)
        props.setdefault("sentiment", 0.0)
        props.setdefault("confidence", 0.8)
        props.setdefault("source", "agent")
        
        with self.session() as session:
            # Always CREATE (not MERGE) to allow multiple relationships
            session.run(
                """
                MATCH (source:Entity {id: $source_id})
                MATCH (target:Entity {id: $target_id})
                CREATE (source)-[r:RELATES_TO]->(target)
                SET r = $props
                """,
                source_id=str(source_id),
                target_id=str(target_id),
                props=props,
            )
            logger.debug(f"Created relationship {source_id} -[{relationship_type}]-> {target_id} (id: {rel_id})")
            return rel_id
    
    def get_relationships(self, entity_id: str | UUID, direction: str = "both") -> list[dict[str, Any]]:
        """
        Get relationships for an entity.
        
        direction: 'outgoing', 'incoming', or 'both'
        """
        with self.session() as session:
            if direction == "outgoing":
                query = """
                    MATCH (e:Entity {id: $id})-[r:RELATES_TO]->(other)
                    RETURN r, other.id as other_id, other.name as other_name
                """
            elif direction == "incoming":
                query = """
                    MATCH (e:Entity {id: $id})<-[r:RELATES_TO]-(other)
                    RETURN r, other.id as other_id, other.name as other_name
                """
            else:
                query = """
                    MATCH (e:Entity {id: $id})-[r:RELATES_TO]-(other)
                    RETURN r, other.id as other_id, other.name as other_name
                """
            
            result = session.run(query, id=str(entity_id))
            relationships = []
            for record in result:
                rel = dict(record["r"])
                rel["other_id"] = record["other_id"]
                rel["other_name"] = record["other_name"]
                relationships.append(rel)
            
            return relationships
    
    def store_embedding(self, entity_id: str | UUID, embedding: list[float]) -> None:
        """Store a vector embedding for an entity."""
        with self.session() as session:
            session.run(
                """
                MATCH (e:Entity {id: $id})
                SET e.embedding = $embedding
                """,
                id=str(entity_id),
                embedding=embedding,
            )
            logger.debug(f"Stored embedding for {entity_id}")
    
    def vector_search(
        self,
        embedding: list[float],
        limit: int = 10,
        entity_type: EntityType | str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform vector similarity search.
        
        Returns entities ordered by cosine similarity.
        """
        with self.session() as session:
            if entity_type:
                label = self._get_label(entity_type)
                query = f"""
                    CALL db.index.vector.queryNodes('entity_embeddings', $limit, $embedding)
                    YIELD node, score
                    WHERE node:{label}
                    RETURN node, score
                    ORDER BY score DESC
                """
            else:
                query = """
                    CALL db.index.vector.queryNodes('entity_embeddings', $limit, $embedding)
                    YIELD node, score
                    RETURN node, score
                    ORDER BY score DESC
                """
            
            try:
                result = session.run(query, limit=limit, embedding=embedding)
                return [
                    {"entity": dict(record["node"]), "score": record["score"]}
                    for record in result
                ]
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                return []
    
    def fulltext_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Perform full-text search across entities.
        """
        with self.session() as session:
            try:
                result = session.run(
                    """
                    CALL db.index.fulltext.queryNodes('entity_search', $query)
                    YIELD node, score
                    RETURN node, score
                    ORDER BY score DESC
                    LIMIT $limit
                    """,
                    query=query,
                    limit=limit,
                )
                return [
                    {"entity": dict(record["node"]), "score": record["score"]}
                    for record in result
                ]
            except Exception as e:
                logger.error(f"Full-text search failed: {e}")
                return []
    
    def get_graph_neighborhood(
        self,
        entity_id: str | UUID,
        depth: int = 2,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Get the neighborhood graph around an entity.
        
        Returns nodes and edges up to 'depth' hops away.
        """
        with self.session() as session:
            result = session.run(
                f"""
                MATCH path = (e:Entity {{id: $id}})-[*1..{depth}]-(connected)
                WITH e, connected, relationships(path) as rels
                LIMIT $limit
                RETURN 
                    collect(DISTINCT connected) as nodes,
                    collect(DISTINCT rels) as edges
                """,
                id=str(entity_id),
                limit=limit,
            )
            record = result.single()
            if record:
                return {
                    "center": entity_id,
                    "nodes": [dict(n) for n in record["nodes"]],
                    "edges": record["edges"],
                }
            return {"center": entity_id, "nodes": [], "edges": []}
    
    def find_similar_entities(
        self,
        name: str,
        entity_type: EntityType | str | None = None,
        threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        Find entities with similar names.
        
        Uses Levenshtein distance for fuzzy matching.
        """
        with self.session() as session:
            if entity_type:
                label = self._get_label(entity_type)
                query = f"""
                    MATCH (e:{label})
                    WHERE e.name IS NOT NULL
                    WITH e, apoc.text.levenshteinSimilarity(toLower(e.name), toLower($name)) as similarity
                    WHERE similarity > $threshold
                    RETURN e, similarity
                    ORDER BY similarity DESC
                    LIMIT 10
                """
            else:
                query = """
                    MATCH (e:Entity)
                    WHERE e.name IS NOT NULL
                    WITH e, apoc.text.levenshteinSimilarity(toLower(e.name), toLower($name)) as similarity
                    WHERE similarity > $threshold
                    RETURN e, similarity
                    ORDER BY similarity DESC
                    LIMIT 10
                """
            
            try:
                result = session.run(query, name=name, threshold=threshold)
                return [
                    {"entity": dict(record["e"]), "similarity": record["similarity"]}
                    for record in result
                ]
            except Exception as e:
                logger.warning(f"Similarity search failed (APOC may not be installed): {e}")
                return []
    
    def get_stale_relationships(self, days: int) -> list[dict[str, Any]]:
        """
        Find relationships without recent interaction.
        
        Used for open loop detection.
        """
        from datetime import timedelta
        threshold = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Person)-[r:RELATES_TO]-(other:Person)
                WHERE r.last_interaction < $threshold OR r.last_interaction IS NULL
                RETURN p, r, other
                """,
                threshold=threshold,
            )
            return [
                {
                    "person": dict(record["p"]),
                    "relationship": dict(record["r"]),
                    "other": dict(record["other"]),
                }
                for record in result
            ]
    
    def get_stale_projects(self, days: int) -> list[dict[str, Any]]:
        """Find projects without recent activity."""
        from datetime import timedelta
        threshold = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self.session() as session:
            result = session.run(
                """
                MATCH (p:Project)
                WHERE p.status = 'active' 
                  AND (p.last_activity < $threshold OR p.last_activity IS NULL)
                RETURN p
                """,
                threshold=threshold,
            )
            return [dict(record["p"]) for record in result]
    
    def rebuild_from_documents(self, documents: list[dict[str, Any]]) -> int:
        """
        Rebuild the graph from markdown documents.
        
        Returns the number of nodes created.
        """
        count = 0
        
        for doc in documents:
            metadata = doc["metadata"]
            entity_type = metadata.get("type", "note")
            
            # Create node
            with self.session() as session:
                label = self._get_label(entity_type)
                session.run(
                    f"""
                    MERGE (e:Entity:{label} {{id: $id}})
                    SET e += $props
                    """,
                    id=metadata.get("id"),
                    props=metadata,
                )
            count += 1
            
            # Create relationships from wikilinks
            from soml.storage.markdown import MarkdownStore
            md_store = MarkdownStore()
            wikilinks = md_store.parse_wikilinks(doc["content"])
            
            for target_id, _ in wikilinks:
                self.create_relationship(
                    source_id=metadata.get("id"),
                    target_id=target_id,
                    relationship_type="references",
                    category=RelationshipCategory.STRUCTURAL,
                )
        
        logger.info(f"Rebuilt graph with {count} nodes")
        return count
    
    # =========================================================================
    # Document Node Operations
    # =========================================================================
    
    def upsert_document_node(
        self,
        doc_id: str,
        title: str,
        doc_type: str,
        parent_entity_id: str | None = None,
        parent_relationship_id: str | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        """
        Create or update a Document node in the graph.
        
        Documents are first-class nodes for semantic traversal, connected to:
        - Parent entity via :BELONGS_TO
        - Parent relationship via :BELONGS_TO (to relationship node)
        - Tags via :HAS_TAG
        - Referenced entities via :REFERENCES
        """
        props = {
            "id": doc_id,
            "title": title,
            "doc_type": doc_type,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        with self.session() as session:
            # Create/update document node
            if embedding:
                props["embedding"] = embedding
            
            session.run(
                """
                MERGE (d:Document {id: $id})
                SET d += $props
                """,
                id=doc_id,
                props=props,
            )
            
            # Create :BELONGS_TO relationship to parent entity if provided
            if parent_entity_id:
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MATCH (e:Entity {id: $entity_id})
                    MERGE (d)-[:BELONGS_TO]->(e)
                    """,
                    doc_id=doc_id,
                    entity_id=parent_entity_id,
                )
            
            # Store parent_relationship_id as a property on the document node
            # (Neo4j relationships are edges, not nodes, so we store as property)
            if parent_relationship_id:
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    SET d.parent_relationship_id = $rel_id
                    """,
                    doc_id=doc_id,
                    rel_id=parent_relationship_id,
                )
            
            logger.debug(f"Upserted document node {doc_id}: {title}")
    
    def delete_document_node(self, doc_id: str) -> bool:
        """Delete a Document node and all its relationships."""
        with self.session() as session:
            result = session.run(
                "MATCH (d:Document {id: $id}) DETACH DELETE d RETURN count(d) as deleted",
                id=doc_id,
            )
            record = result.single()
            deleted = record["deleted"] > 0 if record else False
            
            if deleted:
                logger.debug(f"Deleted document node {doc_id}")
            
            return deleted
    
    def sync_document_references(self, doc_id: str, referenced_entity_ids: list[str]) -> None:
        """
        Sync :REFERENCES edges from a document to entities.
        
        Called after parsing wikilinks from document content.
        Removes old references and creates new ones.
        """
        with self.session() as session:
            # Remove existing references
            session.run(
                """
                MATCH (d:Document {id: $doc_id})-[r:REFERENCES]->()
                DELETE r
                """,
                doc_id=doc_id,
            )
            
            # Create new references
            for entity_id in referenced_entity_ids:
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MATCH (e:Entity {id: $entity_id})
                    MERGE (d)-[:REFERENCES]->(e)
                    """,
                    doc_id=doc_id,
                    entity_id=entity_id,
                )
            
            logger.debug(f"Synced {len(referenced_entity_ids)} references for document {doc_id}")
    
    def store_document_embedding(self, doc_id: str, embedding: list[float]) -> None:
        """Store a vector embedding for a document."""
        with self.session() as session:
            session.run(
                """
                MATCH (d:Document {id: $id})
                SET d.embedding = $embedding
                """,
                id=doc_id,
                embedding=embedding,
            )
            logger.debug(f"Stored embedding for document {doc_id}")
    
    # =========================================================================
    # Tag Node Operations
    # =========================================================================
    
    def ensure_tag_node(self, tag_name: str, color: str | None = None) -> None:
        """
        Ensure a Tag node exists in the graph.
        
        Tags are shared across entities and documents.
        """
        props = {
            "name": tag_name,
            "created_at": datetime.now().isoformat(),
        }
        if color:
            props["color"] = color
        
        with self.session() as session:
            session.run(
                """
                MERGE (t:Tag {name: $name})
                ON CREATE SET t += $props
                """,
                name=tag_name,
                props=props,
            )
            logger.debug(f"Ensured tag node: {tag_name}")
    
    def sync_item_tags(
        self,
        item_id: str,
        item_type: str,  # "entity" or "document"
        tags: list[str],
    ) -> None:
        """
        Sync :HAS_TAG edges for an entity or document.
        
        Removes old tags and creates new ones.
        """
        label = "Entity" if item_type == "entity" else "Document"
        
        with self.session() as session:
            # Remove existing tag relationships
            session.run(
                f"""
                MATCH (n:{label} {{id: $item_id}})-[r:HAS_TAG]->()
                DELETE r
                """,
                item_id=item_id,
            )
            
            # Create new tag relationships
            for tag_name in tags:
                # Ensure tag exists
                self.ensure_tag_node(tag_name)
                
                # Create relationship
                session.run(
                    f"""
                    MATCH (n:{label} {{id: $item_id}})
                    MATCH (t:Tag {{name: $tag_name}})
                    MERGE (n)-[:HAS_TAG]->(t)
                    """,
                    item_id=item_id,
                    tag_name=tag_name,
                )
            
            logger.debug(f"Synced {len(tags)} tags for {item_type} {item_id}")
    
    def add_item_tags(
        self,
        item_id: str,
        item_type: str,  # "entity" or "document"
        tags: list[str],
    ) -> None:
        """Add tags to an entity or document without removing existing ones."""
        label = "Entity" if item_type == "entity" else "Document"
        
        with self.session() as session:
            for tag_name in tags:
                self.ensure_tag_node(tag_name)
                session.run(
                    f"""
                    MATCH (n:{label} {{id: $item_id}})
                    MATCH (t:Tag {{name: $tag_name}})
                    MERGE (n)-[:HAS_TAG]->(t)
                    """,
                    item_id=item_id,
                    tag_name=tag_name,
                )
    
    def remove_item_tags(
        self,
        item_id: str,
        item_type: str,  # "entity" or "document"
        tags: list[str],
    ) -> None:
        """Remove specific tags from an entity or document."""
        label = "Entity" if item_type == "entity" else "Document"
        
        with self.session() as session:
            for tag_name in tags:
                session.run(
                    f"""
                    MATCH (n:{label} {{id: $item_id}})-[r:HAS_TAG]->(t:Tag {{name: $tag_name}})
                    DELETE r
                    """,
                    item_id=item_id,
                    tag_name=tag_name,
                )
    
    def delete_orphan_tags(self) -> int:
        """
        Delete Tag nodes that have no incoming :HAS_TAG edges.
        
        Returns count of deleted tags.
        """
        with self.session() as session:
            result = session.run(
                """
                MATCH (t:Tag)
                WHERE NOT ()-[:HAS_TAG]->(t)
                DELETE t
                RETURN count(t) as deleted
                """
            )
            record = result.single()
            deleted = record["deleted"] if record else 0
            
            if deleted > 0:
                logger.info(f"Deleted {deleted} orphan tags")
            
            return deleted
    
    # =========================================================================
    # Graph Traversal Queries
    # =========================================================================
    
    def find_by_tag(
        self,
        tag_name: str,
        include_entities: bool = True,
        include_documents: bool = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Find all entities and/or documents with a specific tag.
        """
        results = []
        
        with self.session() as session:
            if include_entities:
                entity_result = session.run(
                    """
                    MATCH (e:Entity)-[:HAS_TAG]->(t:Tag {name: $tag_name})
                    RETURN e, 'entity' as item_type
                    LIMIT $limit
                    """,
                    tag_name=tag_name,
                    limit=limit,
                )
                for record in entity_result:
                    results.append({
                        "item": dict(record["e"]),
                        "item_type": "entity",
                    })
            
            if include_documents:
                remaining = limit - len(results)
                if remaining > 0:
                    doc_result = session.run(
                        """
                        MATCH (d:Document)-[:HAS_TAG]->(t:Tag {name: $tag_name})
                        RETURN d, 'document' as item_type
                        LIMIT $limit
                        """,
                        tag_name=tag_name,
                        limit=remaining,
                    )
                    for record in doc_result:
                        results.append({
                            "item": dict(record["d"]),
                            "item_type": "document",
                        })
        
        return results
    
    def find_related_by_tags(
        self,
        entity_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Find entities and documents that share tags with a given entity.
        """
        with self.session() as session:
            result = session.run(
                """
                MATCH (source:Entity {id: $entity_id})-[:HAS_TAG]->(t:Tag)<-[:HAS_TAG]-(related)
                WHERE related.id <> $entity_id
                WITH related, collect(DISTINCT t.name) as shared_tags, count(t) as tag_count
                RETURN related, shared_tags, tag_count,
                       CASE WHEN 'Document' IN labels(related) THEN 'document' ELSE 'entity' END as item_type
                ORDER BY tag_count DESC
                LIMIT $limit
                """,
                entity_id=entity_id,
                limit=limit,
            )
            
            return [
                {
                    "item": dict(record["related"]),
                    "item_type": record["item_type"],
                    "shared_tags": record["shared_tags"],
                    "tag_count": record["tag_count"],
                }
                for record in result
            ]
    
    def find_documents_referencing(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Find all documents that reference a specific entity via wikilinks.
        """
        with self.session() as session:
            result = session.run(
                """
                MATCH (d:Document)-[:REFERENCES]->(e:Entity {id: $entity_id})
                RETURN d
                LIMIT $limit
                """,
                entity_id=entity_id,
                limit=limit,
            )
            
            return [dict(record["d"]) for record in result]
    
    def find_documents_for_entity(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Find all documents that belong to an entity.
        """
        with self.session() as session:
            result = session.run(
                """
                MATCH (d:Document)-[:BELONGS_TO]->(e:Entity {id: $entity_id})
                RETURN d
                ORDER BY d.updated_at DESC
                LIMIT $limit
                """,
                entity_id=entity_id,
                limit=limit,
            )
            
            return [dict(record["d"]) for record in result]
    
    def find_documents_for_relationship(self, relationship_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Find all documents that belong to a relationship.
        """
        with self.session() as session:
            result = session.run(
                """
                MATCH (d:Document)
                WHERE d.parent_relationship_id = $relationship_id
                RETURN d
                ORDER BY d.updated_at DESC
                LIMIT $limit
                """,
                relationship_id=relationship_id,
                limit=limit,
            )
            
            return [dict(record["d"]) for record in result]
    
    def get_item_tags(self, item_id: str, item_type: str = "entity") -> list[str]:
        """Get all tags for an entity or document."""
        label = "Entity" if item_type == "entity" else "Document"
        
        with self.session() as session:
            result = session.run(
                f"""
                MATCH (n:{label} {{id: $item_id}})-[:HAS_TAG]->(t:Tag)
                RETURN t.name as tag_name
                """,
                item_id=item_id,
            )
            
            return [record["tag_name"] for record in result]
    
    def document_vector_search(
        self,
        embedding: list[float],
        limit: int = 10,
        parent_entity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform vector similarity search on documents.
        
        Returns documents ordered by cosine similarity.
        """
        with self.session() as session:
            if parent_entity_id:
                query = """
                    MATCH (d:Document)-[:BELONGS_TO]->(e:Entity {id: $entity_id})
                    WHERE d.embedding IS NOT NULL
                    WITH d, gds.similarity.cosine(d.embedding, $embedding) as score
                    RETURN d, score
                    ORDER BY score DESC
                    LIMIT $limit
                """
                params = {"embedding": embedding, "limit": limit, "entity_id": parent_entity_id}
            else:
                # Use vector index if available
                try:
                    result = session.run(
                        """
                        CALL db.index.vector.queryNodes('document_embeddings', $limit, $embedding)
                        YIELD node, score
                        RETURN node as d, score
                        ORDER BY score DESC
                        """,
                        limit=limit,
                        embedding=embedding,
                    )
                    return [
                        {"document": dict(record["d"]), "score": record["score"]}
                        for record in result
                    ]
                except Exception:
                    # Fall back to brute force if index doesn't exist
                    query = """
                        MATCH (d:Document)
                        WHERE d.embedding IS NOT NULL
                        WITH d, gds.similarity.cosine(d.embedding, $embedding) as score
                        RETURN d, score
                        ORDER BY score DESC
                        LIMIT $limit
                    """
                    params = {"embedding": embedding, "limit": limit}
            
            try:
                result = session.run(query, **params)
                return [
                    {"document": dict(record["d"]), "score": record["score"]}
                    for record in result
                ]
            except Exception as e:
                logger.error(f"Document vector search failed: {e}")
                return []

