from fastmcp import FastMCP, Client
from contextlib import asynccontextmanager

# Server instance for tool registration
mcp_server = FastMCP("StoryboardToolServer")

# IMPORTANT: Do not remove these imports
# Import tool modules to register tools via decorators
# This must happen after mcp_server is defined
from agent_tools import user_interface_tool, image_generation_tool, query_tools

@asynccontextmanager
async def get_mcp_client():
    """
    Get MCP client for in-memory testing and internal tool calls.

    Usage:
        async with get_mcp_client() as client:
            result = await client.call_tool("tool_name", {"param": "value"})
    """
    async with Client(mcp_server) as client:
        yield client

# Create a global client instance
# Note: This client must be initialized before calling tools
_mcp_client_instance = None

async def get_global_mcp_client():
    """
    Get or initialize the global MCP client instance.
    This ensures the client is properly initialized before use.
    """
    global _mcp_client_instance
    if _mcp_client_instance is None:
        _mcp_client_instance = Client(mcp_server)
        await _mcp_client_instance.__aenter__()
    return _mcp_client_instance

async def close_global_mcp_client():
    """
    Close the global MCP client instance.
    Should be called during application shutdown.
    """
    global _mcp_client_instance
    if _mcp_client_instance is not None:
        await _mcp_client_instance.__aexit__(None, None, None)
        _mcp_client_instance = None