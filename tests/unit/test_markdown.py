"""Tests for markdown storage."""

import pytest
from pathlib import Path
from uuid import uuid4

from soml.core.types import Person, Project, Note, Source
from soml.storage.markdown import MarkdownStore


class TestMarkdownStore:
    """Tests for MarkdownStore."""
    
    def test_write_and_read_person(self, temp_data_dir):
        """Test writing and reading a person."""
        store = MarkdownStore(temp_data_dir)
        
        person = Person(
            name="Cayden",
            disambiguator="Atitan board member",
            source=Source.AGENT,
            confidence=0.9,
        )
        
        # Write
        path = store.write(person)
        assert path.exists()
        assert path.suffix == ".md"
        
        # Read
        doc = store.read(path)
        assert doc is not None
        assert doc["metadata"]["name"] == "Cayden"
        assert doc["metadata"]["disambiguator"] == "Atitan board member"
        assert "# Cayden" in doc["content"]
    
    def test_write_and_read_note(self, temp_data_dir):
        """Test writing and reading a note."""
        store = MarkdownStore(temp_data_dir)
        
        note = Note(
            title="Meeting notes",
            content="Discussed investment strategy with the team.",
        )
        
        # Write
        path = store.write(note)
        assert path.exists()
        
        # Read
        doc = store.read(path)
        assert doc is not None
        assert doc["metadata"]["title"] == "Meeting notes"
        assert "Discussed investment" in doc["content"]
    
    def test_read_by_id(self, temp_data_dir):
        """Test reading a document by ID."""
        store = MarkdownStore(temp_data_dir)
        
        person = Person(name="Marcus")
        path = store.write(person)
        
        # Read by ID
        doc = store.read_by_id(person.id)
        assert doc is not None
        assert doc["metadata"]["name"] == "Marcus"
    
    def test_list_all(self, temp_data_dir):
        """Test listing all documents."""
        store = MarkdownStore(temp_data_dir)
        
        # Write multiple entities
        store.write(Person(name="Alice"))
        store.write(Person(name="Bob"))
        store.write(Project(name="Project X"))
        
        # List all
        all_docs = store.list_all()
        assert len(all_docs) == 3
    
    def test_soft_delete(self, temp_data_dir):
        """Test soft delete."""
        store = MarkdownStore(temp_data_dir)
        
        person = Person(name="ToDelete")
        path = store.write(person)
        assert path.exists()
        
        # Soft delete
        result = store.delete(path, soft=True)
        assert result is True
        assert not path.exists()
        
        # Check it's in .deleted folder
        deleted_files = list((temp_data_dir / ".deleted").glob("*.md"))
        assert len(deleted_files) == 1
    
    def test_parse_wikilinks(self, temp_data_dir):
        """Test wikilink parsing."""
        store = MarkdownStore(temp_data_dir)
        
        content = """
        This note references [[abc-123|Alice]] and [[def-456|Project X]].
        Also has [[simple-link]] without display text.
        """
        
        links = store.parse_wikilinks(content)
        
        assert len(links) == 3
        assert ("abc-123", "Alice") in links
        assert ("def-456", "Project X") in links
        assert ("simple-link", "simple-link") in links
    
    def test_search(self, temp_data_dir):
        """Test simple search."""
        store = MarkdownStore(temp_data_dir)
        
        store.write(Note(content="Meeting with Cayden about Atitan"))
        store.write(Note(content="Random other note"))
        store.write(Person(name="Cayden", notes="Investor"))
        
        # Search
        results = store.search("Cayden")
        
        # Should find the note and person
        assert len(results) >= 1

