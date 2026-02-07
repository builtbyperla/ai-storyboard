"""
Vector database helper module for semantic search on recall entries.
Provides LanceDB-based vector search with native async support.
"""

import os
import pickle
from typing import List, Dict, Any, Optional
from core.app_config import SemanticSearchConfig
import numpy as np

class VectorDB:
    """Low-level vector database primitives: Switched to in-memory to avoid 
       vector DB compatability issues. Left async stubs so it's easy to
       switch out.
    """
    def __init__(self):
        self.threshold = SemanticSearchConfig.SIMILARITY_THRESHOLD
        self.ids = []
        self.embeddings = []
        self.data_dir = "session_data/vectordb_memmap"
        self.data_file = os.path.join(self.data_dir, "vectordb.pkl")

    async def setup(self, clear_db: bool = False):
        """Ensure vector database directory and table exist."""
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        if clear_db:
            # Remove existing file
            if os.path.exists(self.data_file):
                os.remove(self.data_file)
            self.ids = []
            self.embeddings = []
        else:
            # Load existing data if file exists
            if os.path.exists(self.data_file):
                with open(self.data_file, 'rb') as f:
                    data = pickle.load(f)
                    self.ids = data.get('ids', [])
                    self.embeddings = data.get('embeddings', [])

    async def ensure_initialized(self):
        """Lazy initialization of async connection and table."""
        pass

    async def add(self, ids: List[str], embeddings: List[List[float]]) -> None:
        """Add or update vectors."""
        await self.ensure_initialized()

        if len(ids) != len(embeddings):
            raise ValueError(f"Mismatch: {len(ids)} ids but {len(embeddings)} embeddings")

        # Add IDs and add normalized embedding vectors as numpy arrays
        self.ids.extend(ids)
        for embedding in embeddings:
            embedding_array = np.array(embedding)
            norm = np.linalg.norm(embedding_array)
            if norm > 0:
                normalized_embedding = embedding_array / norm
            else:
                normalized_embedding = embedding_array
            self.embeddings.append(normalized_embedding)
        
        await self.save_db()

    async def query(self, query_embeddings: List[List[float]], n_results: int = 5) -> Dict[str, Any]:
        """Query for similar vectors by ID."""
        await self.ensure_initialized()
        
        if not self.embeddings or not query_embeddings:
            return {'ids': [], 'distances': []}
        
        # Safety check: ensure ids and embeddings are aligned
        if len(self.ids) != len(self.embeddings):
            raise ValueError(f"Data corruption: {len(self.ids)} ids but {len(self.embeddings)} embeddings")
        
        all_ids = []
        all_distances = []
        
        # Process each query embedding
        for query_embedding in query_embeddings:
            query_vector = np.array(query_embedding)
            
            # Normalize query vector
            query_norm = np.linalg.norm(query_vector)
            if query_norm > 0:
                norm_query = query_vector / query_norm
            else:
                # Skip this embedding if norm is 0
                all_ids.append([])
                all_distances.append([])
                continue
            
            # Compute cosine similarities with all stored embeddings
            similarities = []
            for i, embedding in enumerate(self.embeddings):
                # Since stored embeddings are already normalized numpy arrays, cosine similarity is just dot product
                similarity = np.dot(norm_query, embedding)
                similarities.append((similarity, i))
            
            # Sort by similarity (highest first), filter by minimum threshold, then get top n_results
            similarities.sort(reverse=True, key=lambda x: x[0])
            similarities = [(sim, idx) for sim, idx in similarities if sim >= self.threshold]
            top_results = similarities[:n_results]
            
            # Extract IDs and distances (convert similarity to distance: 1 - similarity)
            result_ids = [self.ids[idx] for _, idx in top_results]
            result_distances = [1.0 - sim for sim, _ in top_results]
            
            all_ids.append(result_ids)
            all_distances.append(result_distances)
        
        return {'ids': all_ids, 'distances': all_distances}

    async def count(self) -> int:
        """Return the total number of vectors."""
        await self.ensure_initialized()

        return len(self.ids)

    async def reset_collection(self) -> None:
        """Delete all vectors."""
        await self.ensure_initialized()

        self.ids = []
        self.embeddings = []

    async def close(self):
        await self.save_db()

    async def save_db(self):
        """Save ids and embeddings to persistent storage."""
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Save both ids and embeddings in a single pickle file
        data = {
            'ids': self.ids,
            'embeddings': self.embeddings
        }
        with open(self.data_file, 'wb') as f:
            pickle.dump(data, f)
    

vector_db = VectorDB()