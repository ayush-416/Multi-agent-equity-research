"""
FAISS vector store for document embeddings.

Simple wrapper around FAISS for storing and retrieving document embeddings.
"""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import faiss

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """Simple FAISS-based vector store for document retrieval."""

    def __init__(self, dimension: int = 768):
        """
        Initialize FAISS vector store.

        Args:
            dimension: Embedding dimension (768 for Gemini)
        """
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
        self.documents = []  # Store document chunks with metadata
        self.id_to_doc_map = {}  # Map FAISS ID to document index

    def add_documents(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]]
    ) -> None:
        """
        Add documents to the vector store.

        Args:
            texts: List of document texts
            embeddings: List of embedding vectors
            metadatas: List of metadata dicts for each document
        """
        if not texts or not embeddings or not metadatas:
            logger.warning("Empty input provided to add_documents")
            return

        if len(texts) != len(embeddings) or len(texts) != len(metadatas):
            raise ValueError("texts, embeddings, and metadatas must have the same length")

        # Convert embeddings to numpy array and normalize for cosine similarity
        embeddings_array = np.array(embeddings, dtype=np.float32)

        # Normalize vectors for cosine similarity (required for IndexFlatIP)
        norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
        embeddings_array = embeddings_array / norms

        # Add to FAISS index
        start_id = self.index.ntotal
        self.index.add(embeddings_array)

        # Store documents with metadata
        for i, (text, metadata) in enumerate(zip(texts, metadatas)):
            doc_id = len(self.documents)
            self.documents.append({
                "text": text,
                "metadata": metadata
            })
            self.id_to_doc_map[start_id + i] = doc_id

        logger.info(f"Added {len(texts)} documents to vector store (total: {self.index.ntotal})")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of top results to return

        Returns:
            List of dicts with 'text', 'metadata', and 'score' keys
        """
        if self.index.ntotal == 0:
            logger.warning("Vector store is empty")
            return []

        # Normalize query vector
        query_array = np.array([query_embedding], dtype=np.float32)
        query_norm = np.linalg.norm(query_array)
        query_array = query_array / query_norm

        # Search
        top_k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_array, top_k)

        # Build results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for missing results
                continue

            doc_id = self.id_to_doc_map.get(int(idx))
            if doc_id is None:
                logger.warning(f"Document not found for FAISS index {idx}")
                continue

            doc = self.documents[doc_id]
            results.append({
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": float(score)
            })

        return results

    def save(self, directory: Path) -> None:
        """
        Save the vector store to disk.

        Args:
            directory: Directory to save the index and documents
        """
        directory.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        index_path = directory / "index.faiss"
        faiss.write_index(self.index, str(index_path))

        # Save documents and metadata
        docs_path = directory / "documents.pkl"
        with open(docs_path, "wb") as f:
            pickle.dump({
                "documents": self.documents,
                "id_to_doc_map": self.id_to_doc_map,
                "dimension": self.dimension
            }, f)

        logger.info(f"Saved vector store to {directory}")

    @classmethod
    def load(cls, directory: Path) -> "FAISSVectorStore":
        """
        Load a vector store from disk.

        Args:
            directory: Directory containing the saved index

        Returns:
            Loaded FAISSVectorStore instance
        """
        index_path = directory / "index.faiss"
        docs_path = directory / "documents.pkl"

        if not index_path.exists() or not docs_path.exists():
            raise FileNotFoundError(f"Vector store not found in {directory}")

        # Load FAISS index
        index = faiss.read_index(str(index_path))

        # Load documents and metadata
        with open(docs_path, "rb") as f:
            data = pickle.load(f)

        # Create instance and populate
        store = cls(dimension=data["dimension"])
        store.index = index
        store.documents = data["documents"]
        store.id_to_doc_map = data["id_to_doc_map"]

        logger.info(f"Loaded vector store from {directory} ({store.index.ntotal} documents)")

        return store

    def clear(self) -> None:
        """Clear all documents from the vector store."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.documents = []
        self.id_to_doc_map = {}
        logger.info("Cleared vector store")

    @property
    def count(self) -> int:
        """Get the number of documents in the store."""
        return self.index.ntotal

    @property
    def texts(self) -> List[str]:
        """Get all document texts."""
        return [doc["text"] for doc in self.documents]

    @property
    def metadata(self) -> List[Dict[str, Any]]:
        """Get all document metadata."""
        return [doc["metadata"] for doc in self.documents]
