"""
User Interface Tool (Agent Tools Wrapper)

Uses FastMCP's Tool.from_function() utility for metadata extraction.
Provides clean namespace for UI-specific tools with no duplication.

The core logic lives in handlers/user_interface.py - this file just wraps
handler methods as tools using FastMCP's metadata extraction.
"""

from handlers.user_interface import UserInterfaceHandler
from pydantic import Field, BaseModel
from typing import Optional, Annotated, TypedDict
from agent_tools.mcp_client import mcp_server
from common.tool_args import ToolArgModel
from typing_extensions import NotRequired

# ============================================================================
# PYDANTIC MODELS (for complex nested structures)
# ============================================================================

CardID = Annotated[str, Field(description="Card ID")]
CardTitle = Annotated[str, Field(description="Title of card")]
CardText = Annotated[str, Field(description="Text description of card")]
OptionalImageID = Annotated[Optional[str], Field(description="Image ID")]
RequiredImageID = Annotated[str, Field(description="Image ID")]
CardX = Annotated[int, Field(description="X position for card in free canvas")]
CardY = Annotated[int, Field(description="Y position for card in free canvas")]

class CanvasCard(BaseModel):
    """ Card to add to canvas """
    title: Optional[CardTitle] = None
    text: Optional[CardText] = None
    image_id: OptionalImageID = None
    x: Optional[CardX] = None
    y: Optional[CardY] = None

class CardUpdate(BaseModel):
    """
    Update to make to a card in canvas.
    Only fields that are explicitly provided will be updated.
    Omitted fields preserve existing values.
    """
    id: CardID
    title: Optional[CardTitle] = None
    text: Optional[CardText] = None
    image_id: OptionalImageID = None
    x: Optional[CardX] = None
    y: Optional[CardY] = None

class PreviewCard(BaseModel):
    """ Card to add to preview pane """
    id: Optional[CardID] = None
    image_id: Optional[RequiredImageID] = None
    title: Optional[CardText] = ""

class PreviewCardUpdate(BaseModel):
    """
    Update to make for card in preview pane.
    Only fields that are explicitly provided will be updated.
    Omitted fields preserve existing values.
    """
    id: CardID
    image_id: OptionalImageID = None
    title: Optional[CardText] = None

class GridCardPlacement(BaseModel):
    """
    Specifies a card's position in a grid layout.
    Row and column indices are 1-indexed.
    """
    card_id: CardID
    row: Annotated[int, Field(description="Row position (1-indexed)", ge=1)]
    col: Annotated[int, Field(description="Column position (1-indexed)", ge=1)]

# ============================================================================
# USER INTERFACE TOOL
# ============================================================================

class UserInterfaceTool:
    """
        Agent tools for communicating changes to the frontend.
    """

    # ------------------------------------------------------------------------
    # CANVAS OPERATIONS
    # ------------------------------------------------------------------------

    @staticmethod
    @mcp_server.tool
    async def get_board_state() -> dict:
        """
        Get the current state of the board canvas and preview pane.
        """
        return await UserInterfaceHandler.get_board_state()

    @staticmethod
    @mcp_server.tool
    async def add_cards_to_canvas(
        cards: Annotated[list[CanvasCard], Field(description="List of cards to add to canvas")]
    ) -> dict:
        """
        Add multiple cards to the canvas.
        """
        return await UserInterfaceHandler._send_command("add_cards_to_canvas", cards=cards)

    @staticmethod
    @mcp_server.tool
    async def update_cards_in_canvas(
        cards: Annotated[list[CardUpdate], Field(description="List of card updates to apply (by ID)")]
    ) -> dict:
        """
        Update content and/or position of multiple canvas cards by ID.
        Only provided fields are updated - omitted fields remain unchanged.
        """
        # Validate with pydantic, but pass raw dicts to avoid null overrides
        return await UserInterfaceHandler._send_command("update_cards_in_canvas", cards=cards)

    @staticmethod
    @mcp_server.tool
    async def delete_cards_from_canvas(
        card_ids: Annotated[list[CardID], Field(description="List of card IDs to delete")]
    ) -> dict:
        """
        Delete multiple cards from the canvas.
        """
        return await UserInterfaceHandler._send_command("delete_cards_from_canvas", card_ids=card_ids)

    @staticmethod
    # Left this out because the agent used inconsistently, worse UX
    async def grid_tool(
        rows: Annotated[int, Field(description="Number of rows in the grid", ge=1)],
        cols: Annotated[int, Field(description="Number of columns in the grid", ge=1)],
        start_x: Annotated[int, Field(description="Starting X position for the grid")],
        start_y: Annotated[int, Field(description="Starting Y position for the grid")],
        h_spacing: Annotated[int, Field(description="Horizontal spacing between cards in pixels")] = 10,
        v_spacing: Annotated[int, Field(description="Vertical spacing between cards in pixels")] = 10,
        include_existing: Annotated[list[GridCardPlacement], Field(description="List of existing cards to place in the grid with their positions")] = []
    ) -> dict:
        """
        Arrange cards in a grid-like layout on the free-form canvas.
        Creates new cards if they don't exist, and repositions existing ones if they're provided.
        This is NOT a rigid grid system - cards are positioned at calculated coordinates
        but remain independently movable afterward.

        Do not include cards in include_existing if their IDs do not already exist in the current board cards.
        """
        return await UserInterfaceHandler._send_command(
            "create_card_grid",
            rows=rows,
            cols=cols,
            hSpacing=h_spacing,
            vSpacing=v_spacing,
            startX=start_x,
            startY=start_y,
            includeCards=[
                {
                    "cardId": card.card_id,
                    "row": card.row,
                    "col": card.col
                }
                for card in include_existing
            ]
        )

    # ------------------------------------------------------------------------
    # PREVIEW PANE
    # ------------------------------------------------------------------------

    @staticmethod
    @mcp_server.tool
    async def add_preview_cards(
        cards: Annotated[list[PreviewCard], Field(description="List of preview cards to prepend to the preview pane")]
    ) -> dict:
        """
        Add preview cards to the beginning of the preview pane.
        Cards are prepended in a free-flowing list. Each card gets a unique ID if not provided.
        """
        return await UserInterfaceHandler._send_command("add_preview_cards", cards=cards)

    @staticmethod
    @mcp_server.tool
    async def update_preview_cards(
        updates: Annotated[list[PreviewCardUpdate], Field(description="List of card updates to apply (by ID)")]
    ) -> dict:
        """
        Update existing preview cards by ID.
        Use this to update images or text for specific cards (e.g., when image generation completes).
        Only provided fields are updated - omitted fields remain unchanged.
        """
        return await UserInterfaceHandler._send_command("update_preview_cards", updates=updates)

    @staticmethod
    @mcp_server.tool
    async def remove_preview_cards(
        card_ids: Annotated[list[str], Field(description="List of card IDs to remove from preview pane")]
    ) -> dict:
        """
        Remove specific preview cards by ID.
        Use for complex operations like reordering (remove + add) or cleanup.
        """
        return await UserInterfaceHandler._send_command("remove_preview_cards", card_ids=card_ids)

    # ------------------------------------------------------------------------
    # CANVAS VIEWPORT
    # ------------------------------------------------------------------------

    @staticmethod
    @mcp_server.tool
    async def set_canvas_zoom(
        zoom: Annotated[float, Field(description="Zoom level between 0.25 and 2.0", ge=0.25, le=2.0)]
    ) -> dict:
        """Set the canvas zoom level (0.25 to 2.0)."""
        return await UserInterfaceHandler._send_command("set_canvas_zoom", zoom=zoom)

    @staticmethod
    @mcp_server.tool
    async def set_canvas_pan(
        x: Annotated[float, Field(description="Horizontal offset in pixels")],
        y: Annotated[float, Field(description="Vertical offset in pixels")]
    ) -> dict:
        """Set the canvas pan offset."""
        offset = {"x": x, "y": y}
        return await UserInterfaceHandler._send_command("set_canvas_pan", offset=offset)

    @staticmethod
    @mcp_server.tool
    async def focus_on_cards(
        panel_ids: Annotated[list[str], Field(description="List of panel IDs to focus on")],
        padding: Annotated[Optional[float], Field(description="Padding around focused cards in pixels")] = 50
    ) -> dict:
        """
        Focus the canvas view on specific cards.
        Automatically adjusts zoom and pan to fit cards in view.
        """
        options = {"padding": padding} if padding is not None else None
        return await UserInterfaceHandler._send_command(
            "focus_on_cards",
            panel_ids=panel_ids,
            options=options
        )