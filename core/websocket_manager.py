from enum import Enum
from fastapi import WebSocket
from core.logger_config import logger
import asyncio
import uuid

class SocketNames(Enum):
    CHAT = "chat"
    AUDIO = "audio"
    BRIDGE = "app_bridge"

class WebSocketManager:
    def __init__(self):
        self.connections = {}
        self.pending_responses = {}  # Maps requestId -> asyncio.Future

    def add_connection(self, connection: WebSocket, name: str):
        self.connections[name] = connection

    def remove_connection(self, name):
        del self.connections[name]

    def get_connection(self, name) -> WebSocket:
        return self.connections.get(name)
    
    async def send_message(self, socket_name: SocketNames, message: dict):
        """Sends a message to the specified WebSocket connection."""
        connection = self.get_connection(socket_name)
        if connection:
            await connection.send_json(message)
        else:
            logger.warning(f"[WS Manager] No connection found for {socket_name.value}")

    async def send_and_wait_for_response(self, socket_name: SocketNames, message: dict, timeout: float = 5.0) -> dict:
        """Send a message and wait for the response from frontend.

        Args:
            socket_name: The socket to send on
            message: The message dict to send
            timeout: How long to wait for response (seconds)

        Returns:
            dict with the frontend response data, or None if error occurred
        """
        connection = self.get_connection(socket_name)
        if not connection:
            logger.error(f"[WS Manager] No WebSocket connection for {socket_name.value}")
            return None

        # Generate unique request ID
        request_id = str(uuid.uuid4())
        message['requestId'] = request_id

        # Create future for this request
        future = asyncio.Future()
        self.pending_responses[request_id] = future

        try:
            # Send the message
            await connection.send_json(message)

            # Wait for response with timeout
            frontend_response = await asyncio.wait_for(future, timeout=timeout)

            # Return the frontend response
            if frontend_response and isinstance(frontend_response, dict):
                return frontend_response
            else:
                logger.error(f"[WS Manager] Invalid response type from frontend: {type(frontend_response)}")
                return None

        except asyncio.TimeoutError:
            # Clean up on timeout
            if request_id in self.pending_responses:
                del self.pending_responses[request_id]
            logger.error(f"[WS Manager] No response received within {timeout} seconds for request {request_id}")
            return None
        except Exception as e:
            logger.error(f"[WS Manager] Error sending message: {str(e)}")
            return None

    def resolve_response(self, request_id: str, response: dict):
        """Called by WebSocket handler when a response is received from frontend"""
        if request_id in self.pending_responses:
            future = self.pending_responses.pop(request_id)
            if not future.done():
                future.set_result(response)
        else:
            logger.warning(f"[WS Manager] No pending request found for {request_id}")

socket_manager = WebSocketManager()