"""
Pytest configuration and fixtures for Story of My Life tests.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import pytest

# Set test environment before importing app modules
os.environ["SOML_DATA_DIR"] = tempfile.mkdtemp()
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "somlpassword123"


@pytest.fixture
def temp_data_dir() -> Generator[Path, None, None]:
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        
        # Create directory structure
        for subdir in ["people", "projects", "goals", "events", "notes", "memories", ".deleted", ".index"]:
            (data_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        yield data_dir


@pytest.fixture
def sample_person_data() -> dict:
    """Sample person data for testing."""
    return {
        "id": uuid4(),
        "name": "Cayden",
        "disambiguator": "Atitan board member",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "source": "agent",
        "confidence": 0.9,
        "tags": ["investor", "board"],
        "links": [],
    }


@pytest.fixture
def sample_project_data() -> dict:
    """Sample project data for testing."""
    return {
        "id": uuid4(),
        "name": "Atitan",
        "description": "Investment strategy for Atitan",
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "source": "agent",
        "confidence": 0.85,
        "tags": ["investment", "manufacturing"],
        "stakeholders": [],
        "goals": [],
    }


@pytest.fixture
def sample_note_content() -> str:
    """Sample note content for testing ingestion."""
    return """Met with Cayden yesterday to discuss Atitan investment strategy.
    Determined we will seek a lead investor who can help guide our 
    manufacturing and distribution activities as we just completed 
    final prototypes of the splitR product."""


@pytest.fixture
def sample_timestamps() -> list[dict]:
    """Sample extracted timestamps."""
    from soml.core.types import ExtractedTimestamp
    from datetime import timedelta
    
    return [
        ExtractedTimestamp(
            original_text="yesterday",
            resolved=datetime.now() - timedelta(days=1),
            is_relative=True,
            confidence=0.95,
        )
    ]


@pytest.fixture
def sample_entities() -> list[dict]:
    """Sample extracted entities."""
    from soml.core.types import ExtractedEntity, EntityType
    
    return [
        ExtractedEntity(
            name="Cayden",
            entity_type=EntityType.PERSON,
            context="Atitan board meeting",
            confidence=0.9,
        ),
        ExtractedEntity(
            name="Atitan",
            entity_type=EntityType.PROJECT,
            context="Investment strategy discussion",
            confidence=0.85,
        ),
        ExtractedEntity(
            name="splitR",
            entity_type=EntityType.PROJECT,
            context="Product prototype completed",
            confidence=0.8,
        ),
    ]


@pytest.fixture
def mock_llm_response():
    """Factory for mock LLM responses."""
    def _mock_response(content: str):
        return {
            "choices": [
                {
                    "message": {
                        "content": content,
                    }
                }
            ]
        }
    return _mock_response


# ============================================
# Neo4j Fixtures (require running Neo4j)
# ============================================

@pytest.fixture(scope="session")
def neo4j_driver():
    """Create Neo4j driver for integration tests."""
    try:
        from neo4j import GraphDatabase
        
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "somlpassword123")
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # Test connection
        with driver.session() as session:
            session.run("RETURN 1")
        
        yield driver
        driver.close()
        
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")


@pytest.fixture
def clean_neo4j(neo4j_driver):
    """Clean Neo4j database before each test."""
    with neo4j_driver.session() as session:
        # Delete all nodes and relationships
        session.run("MATCH (n) DETACH DELETE n")
    
    yield neo4j_driver
    
    # Cleanup after test
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

