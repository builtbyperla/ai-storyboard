"""
User Interface Handler

Handles all UI operations with the frontend via WebSocket.
Provides validation, formatting (snake_case → camelCase), and communication.

This handler is stateless and uses static methods - no instantiation needed.
All methods forward commands to the frontend via the WebSocket manager.

Usage:
    from handlers.user_interface import UserInterfaceHandler, CanvasCard

    cards = [CanvasCard(title="Hello", x=100, y=100)]
    response = await UserInterfaceHandler.add_cards_to_canvas(cards)
"""

from core.websocket_manager import socket_manager, SocketNames
from core.logger_config import logger
from pydantic import BaseModel, Field
from typing import Optional
from core.utils.time_utils import get_current_timestamp
import re

# ============================================================================
# USER INTERFACE HANDLER
# ============================================================================

class UserInterfaceHandler:
    """
    Stateless message forwarder to frontend via WebSocket.
    All methods are static - no instantiation needed.

    Responsibilities:
    - Validate input via Pydantic models
    - Convert snake_case to camelCase for JavaScript frontend
    - Send commands to frontend via WebSocket
    - Handle errors and timeouts

    Usage:
        from handlers.user_interface import UserInterfaceHandler

        response = await UserInterfaceHandler.add_cards_to_canvas(cards)
    """

    # ------------------------------------------------------------------------
    # PRIVATE HELPER METHODS
    # ------------------------------------------------------------------------

    @staticmethod
    def _snake_to_camel_case(snake_str: str) -> str:
        """Convert snake_case to camelCase.

        Example:
            snake_to_camel_case('image_id') -> 'imageId'
            snake_to_camel_case('panel_ids') -> 'panelIds'
        """
        return re.sub(r'_([a-z])', lambda match: match.group(1).upper(), snake_str)

    @staticmethod
    def _to_camel_case_dict(obj):
        """Recursively convert objects to camelCase dicts for JavaScript.

        Handles:
        - Pydantic models (converts to dict and recurses)
        - Lists (recurses on each item)
        - Dicts (converts keys and recurses on values)
        - Primitives (returns as-is)

        This ensures Python snake_case is properly converted to JavaScript camelCase
        while maintaining proper nesting structure.
        """
        if isinstance(obj, BaseModel):
            # Pydantic model - convert to dict and recurse
            # Use exclude_unset=True to only include fields that were explicitly provided
            # This allows partial updates without overwriting unspecified fields
            return {
                UserInterfaceHandler._snake_to_camel_case(k): UserInterfaceHandler._to_camel_case_dict(v)
                for k, v in obj.model_dump(exclude_unset=True).items()
            }
        elif isinstance(obj, list):
            return [UserInterfaceHandler._to_camel_case_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {
                UserInterfaceHandler._snake_to_camel_case(k): UserInterfaceHandler._to_camel_case_dict(v)
                for k, v in obj.items()
            }
        else:
            return obj

    @staticmethod
    async def _send_command(command: str, **kwargs) -> dict:
        """
        Core method: Send command to frontend via WebSocket.

        Handles:
        - Parameter conversion (snake_case → camelCase)
        - WebSocket message formatting
        - Error handling and timeout management
        - Response validation

        Args:
            command: Frontend command name (e.g., 'add_cards_to_canvas')
            **kwargs: Parameters (will be converted to camelCase)

        Returns:
            dict with frontend response, or {"error": str, "success": False}
        """
        try:
            # Convert parameters to camelCase
            params = {}
            for key, value in kwargs.items():
                camel_key = UserInterfaceHandler._snake_to_camel_case(key)
                params[camel_key] = UserInterfaceHandler._to_camel_case_dict(value)

            # Build message
            msg = {
                "command": command,
                "params": params,
                "timestamp": get_current_timestamp()
            }

            # Send and wait for response
            response = await socket_manager.send_and_wait_for_response(
                SocketNames.BRIDGE,
                msg,
                timeout=5.0
            )

            if response is None:
                error_msg = f"No response from frontend for command '{command}'"
                logger.error(f"{error_msg}")
                return {"error": error_msg, "success": False}

            if 'state' not in response:
                error_msg = f"Invalid response structure for '{command}': missing 'state'"
                logger.error(f"{error_msg}")
                return {"error": error_msg, "success": False, "response": response}

            # Return just the state part (which contains success flag and result data)
            # instead of the full socket response with requestId, timestamp, etc.
            return response['state']

        except Exception as e:
            error_msg = f"Command '{command}' failed: {str(e)}"
            logger.error(f"{error_msg}")
            return {"error": error_msg, "success": False}

    # ============================================================================
    # COMMON TOOLS - used by both agent and app backend
    # ============================================================================

    async def get_board_state():
        """Get canvas state"""
        return await UserInterfaceHandler._send_command("get_board_state")
