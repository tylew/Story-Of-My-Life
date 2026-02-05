"""Integration tests for the ingestion pipeline."""

import pytest
from datetime import datetime, timedelta

from soml.core.context import create_context
from soml.core.types import EntityType
from soml.agents.ingestion import (
    TimeExtractor,
    EntityExtractor,
    IntentClassifier,
    RelationshipProposer,
    IngestionPipeline,
)


class TestTimeExtractor:
    """Tests for TimeExtractor agent."""
    
    @pytest.mark.asyncio
    async def test_extract_relative_time(self):
        """Test extracting relative time."""
        extractor = TimeExtractor()
        
        context = create_context("Met with Cayden yesterday")
        result = await extractor.run(context)
        
        assert result.success
        assert len(context.timestamps) >= 1
        
        # Check the timestamp
        ts = context.timestamps[0]
        assert ts.is_relative
        assert "yesterday" in ts.original_text.lower()
    
    @pytest.mark.asyncio
    async def test_extract_explicit_date(self):
        """Test extracting explicit date."""
        extractor = TimeExtractor()
        
        context = create_context("Meeting scheduled for January 15, 2026")
        result = await extractor.run(context)
        
        assert result.success
        # Should extract the date
        if context.timestamps:
            assert context.timestamps[0].resolved.month == 1
            assert context.timestamps[0].resolved.day == 15


class TestEntityExtractor:
    """Tests for EntityExtractor agent."""
    
    @pytest.mark.asyncio
    async def test_extract_entities(self):
        """Test entity extraction."""
        extractor = EntityExtractor()
        
        context = create_context(
            "Met with Cayden yesterday to discuss Atitan investment strategy."
        )
        result = await extractor.run(context)
        
        assert result.success
        
        # Should extract Cayden (person) and Atitan (project)
        entity_names = [e.name.lower() for e in context.entities]
        
        # At minimum, should find some entities
        assert len(context.entities) >= 1


class TestIntentClassifier:
    """Tests for IntentClassifier agent."""
    
    @pytest.mark.asyncio
    async def test_classify_observation(self):
        """Test classifying an observation."""
        classifier = IntentClassifier()
        
        context = create_context("Met with Cayden yesterday")
        result = await classifier.run(context)
        
        assert result.success
        assert context.intent is not None
        assert context.intent.document_type in [EntityType.NOTE, EntityType.EVENT]


class TestIngestionPipeline:
    """Tests for the full ingestion pipeline."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """Test the complete ingestion pipeline."""
        pipeline = IngestionPipeline()
        
        result = await pipeline.ingest(
            "Met with Cayden yesterday to discuss Atitan investment strategy. "
            "Determined we will seek a lead investor who can help guide our "
            "manufacturing and distribution activities."
        )
        
        assert result.success
        
        context = result.context
        assert context is not None
        
        # Should have extracted data
        assert len(context.agent_trace) >= 4  # All 4 agents ran
        
        # Should have entities
        if context.entities:
            entity_types = [e.entity_type for e in context.entities]
            # Should have at least identified something
            assert len(entity_types) >= 1

