#!/usr/bin/env python3
"""
Initialize Neo4j schema for Story of My Life.

Creates:
- Node constraints
- Vector index for embeddings
- Full-text search index

Run this script after starting Neo4j:
    python scripts/init_neo4j.py
"""

import os
import sys
import time

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def wait_for_neo4j(uri: str, user: str, password: str, max_retries: int = 30) -> bool:
    """Wait for Neo4j to be ready."""
    print(f"Connecting to Neo4j at {uri}...")
    
    for attempt in range(max_retries):
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            print("✅ Neo4j is ready!")
            return True
        except ServiceUnavailable:
            print(f"⏳ Waiting for Neo4j... (attempt {attempt + 1}/{max_retries})")
            time.sleep(2)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(2)
    
    return False


def init_schema(uri: str, user: str, password: str) -> None:
    """Initialize Neo4j schema."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    try:
        with driver.session() as session:
            print("\n📊 Creating schema...")
            
            # Drop existing constraints/indexes if they exist (for clean restart)
            print("  Clearing existing schema...")
            try:
                session.run("DROP CONSTRAINT entity_id IF EXISTS")
            except Exception:
                pass
            
            # Create unique constraint on entity ID
            print("  Creating entity ID constraint...")
            session.run("""
                CREATE CONSTRAINT entity_id IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.id IS UNIQUE
            """)
            
            # Create constraint on document ID
            print("  Creating document ID constraint...")
            session.run("""
                CREATE CONSTRAINT document_id IF NOT EXISTS
                FOR (d:Document) REQUIRE d.id IS UNIQUE
            """)
            
            # Create vector index for embeddings
            print("  Creating vector index...")
            try:
                session.run("""
                    CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS
                    FOR (e:Entity) ON e.embedding
                    OPTIONS {indexConfig: {
                        `vector.dimensions`: 1536,
                        `vector.similarity_function`: 'cosine'
                    }}
                """)
            except Exception as e:
                print(f"    ⚠️  Vector index may already exist: {e}")
            
            # Create full-text index for search
            print("  Creating full-text index...")
            try:
                session.run("""
                    CREATE FULLTEXT INDEX entity_search IF NOT EXISTS
                    FOR (e:Entity) ON EACH [e.name, e.content, e.title, e.description]
                """)
            except Exception as e:
                print(f"    ⚠️  Full-text index may already exist: {e}")
            
            # Create index on entity type
            print("  Creating type index...")
            session.run("""
                CREATE INDEX entity_type IF NOT EXISTS
                FOR (e:Entity) ON (e.entity_type)
            """)
            
            # Create index on created_at for timeline queries
            print("  Creating timestamp index...")
            session.run("""
                CREATE INDEX entity_created IF NOT EXISTS
                FOR (e:Entity) ON (e.created_at)
            """)
            
            # Create Person-specific indexes
            print("  Creating Person indexes...")
            session.run("""
                CREATE INDEX person_name IF NOT EXISTS
                FOR (p:Person) ON (p.name)
            """)
            
            # Create Project-specific indexes
            print("  Creating Project indexes...")
            session.run("""
                CREATE INDEX project_name IF NOT EXISTS
                FOR (p:Project) ON (p.name)
            """)
            session.run("""
                CREATE INDEX project_status IF NOT EXISTS
                FOR (p:Project) ON (p.status)
            """)
            
            # Create relationship indexes
            print("  Creating relationship indexes...")
            session.run("""
                CREATE INDEX rel_type IF NOT EXISTS
                FOR ()-[r:RELATES_TO]-() ON (r.type)
            """)
            
            print("\n✅ Schema initialization complete!")
            
            # Show created indexes
            print("\n📋 Current indexes:")
            result = session.run("SHOW INDEXES")
            for record in result:
                print(f"   - {record['name']}: {record['type']}")
            
    finally:
        driver.close()


def main() -> None:
    """Main entry point."""
    # Get configuration from environment (with SOML_ prefix)
    uri = os.environ.get("SOML_NEO4J_URI", os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    user = os.environ.get("SOML_NEO4J_USER", os.environ.get("NEO4J_USER", "neo4j"))
    password = os.environ.get("SOML_NEO4J_PASSWORD", os.environ.get("NEO4J_PASSWORD", "somlpassword123"))
    
    print("=" * 50)
    print("Story of My Life - Neo4j Initialization")
    print("=" * 50)
    
    if not wait_for_neo4j(uri, user, password):
        print("❌ Failed to connect to Neo4j")
        sys.exit(1)
    
    init_schema(uri, user, password)
    
    print("\n🎉 Neo4j is ready for Story of My Life!")


if __name__ == "__main__":
    main()

