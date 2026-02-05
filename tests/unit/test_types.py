"""Tests for core types."""

import pytest
from datetime import datetime
from uuid import uuid4

from soml.core.types import (
    Person,
    Project,
    Goal,
    Event,
    Note,
    Memory,
    Relationship,
    RelationshipCategory,
    PersonalRelationshipType,
    StructuralRelationshipType,
    EntityType,
    TemporalState,
    Source,
)


class TestPerson:
    """Tests for Person entity."""
    
    def test_create_person(self):
        """Test basic person creation."""
        person = Person(
            name="Cayden",
            disambiguator="Atitan board member",
        )
        
        assert person.name == "Cayden"
        assert person.disambiguator == "Atitan board member"
        assert person.entity_type == "person"
        assert person.confidence == 0.8  # default
        assert person.source == Source.AGENT  # default
    
    def test_person_with_all_fields(self):
        """Test person with all fields."""
        now = datetime.now()
        person_id = uuid4()
        
        person = Person(
            id=person_id,
            name="Cayden Smith",
            disambiguator="Atitan board member",
            email="cayden@atitan.com",
            phone="+1-555-0123",
            notes="Key advisor for investment strategy",
            last_interaction=now,
            source=Source.USER,
            confidence=1.0,
            tags=["investor", "board"],
        )
        
        assert person.id == person_id
        assert person.email == "cayden@atitan.com"
        assert person.last_interaction == now
        assert person.confidence == 1.0
        assert "investor" in person.tags


class TestProject:
    """Tests for Project entity."""
    
    def test_create_project(self):
        """Test basic project creation."""
        project = Project(
            name="Atitan",
            description="Investment strategy project",
        )
        
        assert project.name == "Atitan"
        assert project.entity_type == "project"
        assert project.status == "active"  # default
    
    def test_project_with_stakeholders(self):
        """Test project with stakeholders."""
        cayden_id = uuid4()
        goal_id = uuid4()
        
        project = Project(
            name="splitR",
            status="active",
            stakeholders=[cayden_id],
            goals=[goal_id],
        )
        
        assert cayden_id in project.stakeholders
        assert goal_id in project.goals


class TestGoal:
    """Tests for Goal entity."""
    
    def test_create_goal(self):
        """Test basic goal creation."""
        goal = Goal(
            title="Secure lead investor",
            description="Find investor for manufacturing guidance",
        )
        
        assert goal.title == "Secure lead investor"
        assert goal.entity_type == "goal"
        assert goal.progress == 0  # default
        assert goal.status == "active"


class TestRelationship:
    """Tests for Relationship entity."""
    
    def test_create_personal_relationship(self):
        """Test personal relationship creation."""
        rel = Relationship(
            source_id=uuid4(),
            target_id=uuid4(),
            category=RelationshipCategory.PERSONAL,
            relationship_type="coworker",
            strength=0.8,
        )
        
        assert rel.category == RelationshipCategory.PERSONAL
        assert rel.relationship_type == "coworker"
        assert rel.strength == 0.8
    
    def test_create_structural_relationship(self):
        """Test structural relationship creation."""
        rel = Relationship(
            source_id=uuid4(),
            target_id=uuid4(),
            category=RelationshipCategory.STRUCTURAL,
            relationship_type="part_of",
            confidence=0.9,
        )
        
        assert rel.category == RelationshipCategory.STRUCTURAL
        assert rel.relationship_type == "part_of"


class TestNote:
    """Tests for Note entity."""
    
    def test_create_note(self):
        """Test note creation."""
        note = Note(
            content="Met with Cayden to discuss Atitan investment",
            title="Meeting notes",
        )
        
        assert note.entity_type == "note"
        assert note.temporal_state == TemporalState.OBSERVED
        assert note.emotional_tone == 0.0  # default neutral
        assert note.urgency == 0  # default
    
    def test_note_with_sentiment(self):
        """Test note with sentiment analysis."""
        note = Note(
            content="Great progress on the prototype!",
            emotional_tone=0.8,
            urgency=20,
        )
        
        assert note.emotional_tone == 0.8
        assert note.urgency == 20

