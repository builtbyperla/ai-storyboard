"""
Base model for FastMCP tool arguments.

This base model prevents Pydantic from generating $defs in JSON schemas
by using json_schema_mode_override configuration.

IMPORTANT: Even with this base model, if you use list[ModelClass] in tool
signatures, FastMCP will still generate $defs. To completely avoid $defs:

1. Use Annotated with Field for simple parameters (preferred):
   ```python
   @mcp.tool()
   async def my_tool(
       name: Annotated[str, Field(description="User name")],
       age: Annotated[int, Field(description="User age", gt=0)]
   ):
       pass
   ```

2. For complex objects, use list[dict] instead of list[Model]:
   ```python
   @mcp.tool()
   async def add_cards(
       cards: Annotated[list[dict], Field(description="List of cards")]
   ):
       # Validate inside the function if needed
       validated_cards = [CanvasCard(**card) for card in cards]
   ```

3. Keep Pydantic models for internal validation only.
"""

from pydantic import BaseModel, ConfigDict


class ToolArgModel(BaseModel):
    """
    Base class for internal Pydantic models (NOT for tool signatures).

    Use this for models that you'll validate internally in your tools,
    but don't expose directly in the tool signature.

    Configured to prevent $defs from appearing in JSON schemas,
    which can cause issues with certain MCP clients.
    """

    model_config = ConfigDict(
        # Prevent $defs from being generated in JSON schema
        json_schema_mode_override='validation',
        # Allow extra fields to be ignored rather than raising errors
        extra='forbid'
    )
