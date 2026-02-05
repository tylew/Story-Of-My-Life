#!/usr/bin/env python3
"""
Rebuild all indices from markdown files.

This script demonstrates the Reconstruction Guarantee:
All derived data (SQLite registry, Neo4j graph, vector embeddings)
can be fully rebuilt from the canonical markdown files.

Usage:
    python scripts/rebuild_indices.py
    python scripts/rebuild_indices.py --data-dir /path/to/data
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from soml.core.config import settings, setup_logging, get_logger
from soml.storage.markdown import MarkdownStore
from soml.storage.registry import RegistryStore
from soml.storage.graph import GraphStore
from soml.agents.storage.vector_embedder import VectorEmbedder

logger = get_logger("rebuild")


async def rebuild_all(data_dir: Path) -> dict:
    """Rebuild all indices from markdown files."""
    logger.info(f"Rebuilding indices from {data_dir}")
    
    results = {
        "documents_scanned": 0,
        "registry_entries": 0,
        "graph_nodes": 0,
        "embeddings": 0,
        "errors": [],
    }
    
    # Initialize stores
    md_store = MarkdownStore(data_dir)
    registry = RegistryStore(data_dir / ".index" / "registry.sqlite")
    graph = GraphStore()
    embedder = VectorEmbedder(graph)
    
    # Scan all markdown files
    documents = []
    for path in md_store.list_all():
        doc = md_store.read(path)
        if doc:
            documents.append(doc)
            results["documents_scanned"] += 1
    
    logger.info(f"Found {len(documents)} documents")
    
    # Rebuild SQLite registry
    print("\n📋 Rebuilding SQLite registry...")
    try:
        count = registry.rebuild_from_directory(data_dir)
        results["registry_entries"] = count
        print(f"   ✓ Indexed {count} documents")
    except Exception as e:
        results["errors"].append(f"Registry rebuild failed: {e}")
        print(f"   ✗ Error: {e}")
    
    # Rebuild Neo4j graph
    print("\n🔗 Rebuilding Neo4j graph...")
    try:
        count = graph.rebuild_from_documents(documents)
        results["graph_nodes"] = count
        print(f"   ✓ Created {count} nodes")
    except Exception as e:
        results["errors"].append(f"Graph rebuild failed: {e}")
        print(f"   ✗ Error: {e}")
    
    # Regenerate embeddings
    print("\n🧠 Regenerating embeddings...")
    try:
        embed_result = await embedder.embed_batch(documents)
        results["embeddings"] = embed_result.get("success", 0)
        print(f"   ✓ Generated {results['embeddings']} embeddings")
    except Exception as e:
        results["errors"].append(f"Embedding failed: {e}")
        print(f"   ✗ Error: {e}")
    
    # Cleanup
    graph.close()
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Rebuild all indices from markdown")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=settings.data_dir,
        help="Path to data directory",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    setup_logging("DEBUG" if args.verbose else "INFO")
    
    print("=" * 50)
    print("Story of My Life - Index Rebuild")
    print("=" * 50)
    print(f"\nData directory: {args.data_dir}")
    
    results = asyncio.run(rebuild_all(args.data_dir))
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"Documents scanned: {results['documents_scanned']}")
    print(f"Registry entries:  {results['registry_entries']}")
    print(f"Graph nodes:       {results['graph_nodes']}")
    print(f"Embeddings:        {results['embeddings']}")
    
    if results["errors"]:
        print(f"\n⚠️  Errors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"   - {error}")
    else:
        print("\n✅ Rebuild complete!")


if __name__ == "__main__":
    main()

