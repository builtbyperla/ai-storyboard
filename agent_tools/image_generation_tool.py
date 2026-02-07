"""
Image Generation Tool (Agent Tools Wrapper)

Uses FastMCP's Tool.from_function() utility for metadata extraction.
Provides clean namespace for image generation tools.

Example usage - replace with your actual handler when ready.
"""

from agent_tools.mcp_client import mcp_server
from common.models import ImageRequest
from handlers.image_generation import image_orchestrator
from db_ops.agent import AgentDB
from pydantic import Field
from typing import Annotated, Optional
from db_ops.app import AppDB

# ============================================================================
# IMAGE GENERATION TOOL NAMESPACE
# ============================================================================

class ImageGenerationTool:
    @staticmethod
    @mcp_server.tool(name='image_generation-request_image')
    async def request_image(
        prompt: Annotated[str, Field(description="Description of image contents")],
        style: Annotated[str, Field(description="Image style description to use")],
        label: Annotated[str, Field(description="Human-readable label such as intro_scene or puppy_jumping")]
    ) -> dict:
        """Generate a single image from a text prompt. DO NOT use the request IDs returned
            from this response as image IDs. They are distinct.

           The app does not do anything with the image once it is complete. You must decide
           what to do with it after it is either reflected in the state snapshot or the app informs you.
        """
        try:
            request = ImageRequest(prompt=prompt, style=style, label=label)
            task_id = await image_orchestrator.request_image(request)
            return {'task_id': task_id}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    @mcp_server.tool(name='image_generation-fetch_statuses')
    async def fetch_statuses(
        ids: Annotated[list[str], Field(description="List of image generation task IDs")]
    ) -> dict:
        """Fetch status for specific image generation tasks. To use this, you must have
        a request ID from a image_generation-request_image response. It will return
        the request status, along with the image ID if successful.
        """
        statuses = await AgentDB.fetch_image_statuses(ids)
        return {'statuses': statuses}