from agent_tools.mcp_client import mcp_server
from handlers.semantic_search import SemanticSearchHandler
from core.app_config import SemanticSearchConfig
from db_ops.agent import AgentDB
from datetime import timedelta

class QueryTools:
    @staticmethod
    @mcp_server.tool
    async def semantic_search(texts: list[str]) -> list:
        """
        Searches for memory entries that are similar to any of the text strings.
        The tool attempts to include context from before and after the matched content.
        Returns a deduplicated, chronologically ordered list of entries with timestamps.
        """
        return await SemanticSearchHandler.search(texts,
                                                SemanticSearchConfig.MIN_MEMORIES,
                                                SemanticSearchConfig.WINDOW_MS)
    
    @staticmethod
    @mcp_server.tool
    async def query_image_cache(image_ids: list[str], include_style=False) -> list:
        """
        Fetches image cache entries for specific image IDs.

        The image style prompt will be included for each image if
        include_style is set to True. Otherwise just the ID and
        content description.
        """
        return await AgentDB.query_image_cache(image_ids, include_style)