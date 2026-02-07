from core.vector_db import vector_db
from db_ops.agent import AgentDB
from db_ops.app import AppDB
from inference.embedding_engine import EmbeddingEngine

class SemanticSearchHandler:
    @staticmethod
    async def search(texts: list[str], n_results: int, window_size_ms: int):
        search_embeddings = await EmbeddingEngine.create_embeddings(texts)
        grouped_entry_ids = await vector_db.query(search_embeddings, n_results)

        # Collect all unique entry IDs across all search queries
        all_entry_ids = set()
        for entry_ids in grouped_entry_ids['ids']:
            all_entry_ids.update(entry_ids)

        # Fetch deduplicated entries with context window - returns single merged list
        deduplicated_entries = await AgentDB.fetch_recall_entries_for_semantic(
            list(all_entry_ids), window_size_ms
        )
        
        return deduplicated_entries
