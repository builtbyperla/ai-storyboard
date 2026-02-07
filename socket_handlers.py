from abc import ABC, abstractmethod
from fastapi import WebSocket, WebSocketDisconnect
from core.websocket_manager import socket_manager, SocketNames
from core.event_manager import event_manager
from core.user_config_manager import user_config_manager
from core.logger_config import logger
from handlers.ui_messaging import MsgStreamerUI
from inference.user_event_handlers import chat_handler as chat_inference_handler
from inference.user_event_handlers import audio_handler as audio_inference_handler
from inference.speech2text import audio_transcriber

import asyncio

class BaseSocketHandler:
    """Base class for WebSocket handlers with lifecycle management"""
    
    def __init__(self, socket_name: SocketNames):
        self.socket_name = socket_name

    async def handle_socket(self, websocket: WebSocket):
        # Accept and register connection with websocket manager
        await websocket.accept()
        socket_manager.add_connection(websocket, self.socket_name)
        logger.info(f"Client connected to {self.socket_name.value}")
        
        # Start listening handler; report disconnects and exceptions
        try:
            await self.start_loop(websocket)
        except WebSocketDisconnect:
            logger.info(f"Client disconnected from {self.socket_name.value}")
        except Exception as e:
            logger.error(f"Error in {self.socket_name.value}: {e}")
            try:
                await websocket.close(code=1011)
            except RuntimeError:
                pass
        finally:
            socket_manager.remove_connection(self.socket_name)

    @abstractmethod
    async def start_loop(self, websocket: WebSocket):
        """Subclasses implement this for per-connection receiving"""
        pass

class ChatSocketHandler(BaseSocketHandler):
    """Handler for chat WebSocket connections"""
    def __init__(self):
        super().__init__(SocketNames.CHAT)

    async def start_loop(self, websocket: WebSocket):
        await self.listen_loop(websocket)

    async def listen_loop(self, websocket: WebSocket):
        # Continuously listens for new chat messages and sends to inference handler
        while True:
            data = await websocket.receive_json()
            msg = data.get('message', '')
            logger.debug(f'Chat message received: {msg}')
            if len(msg) > 0:
                chat_inference_handler.on_new_messages([msg])

class AudioSocketHandler(BaseSocketHandler):
    """Handler for audio WebSocket connections"""
    def __init__(self):
        super().__init__(SocketNames.AUDIO)
        self._chunk_received = asyncio.Event()
        self._transcript_received = asyncio.Event()

        self.audio_chunks_buffer = []
        self.transcripts_for_ui = []

    async def start_loop(self, websocket: WebSocket):
        await asyncio.gather(
            self.listen_loop(websocket),
            self.process_audio_loop(),
            self.ui_transcripts_loop(),
            self.audio_stopped_loop()
        )

    async def listen_loop(self, websocket: WebSocket):
        # Lists for audio chunks from socket and stores in buffer until processed
        while True:
            chunk = await websocket.receive_bytes()
            self.audio_chunks_buffer.append(chunk)
            self._chunk_received.set()
    
    async def process_audio_loop(self):
        # Continuously sends buffered audio chunks to transcriber
        while True:
            # Wait for audio chunks
            await self._chunk_received.wait()
            self._chunk_received.clear()
        
            # Send buffered chunks to audio transcriber and clear
            self.process_buffer()

    def process_buffer(self):
        # Copy buffer and clear
        chunks_to_process = self.audio_chunks_buffer.copy()
        self.audio_chunks_buffer.clear()

        if len(chunks_to_process) == 0:
            return

        # Send chunk(s) to audio transcriber
        if len(chunks_to_process) > 1:
            combined = b''.join(chunks_to_process)
        else:
            combined = chunks_to_process[0]
        asyncio.create_task(audio_transcriber.send_chunk(combined))

    async def ui_transcripts_loop(self):
        # Waits for new transcripts and displays in UI
        while True:
            await self._transcript_received.wait()
            self._transcript_received.clear()
            latest_msg = self.transcripts_for_ui[-1]
            self.transcripts_for_ui = []
            await MsgStreamerUI.update_user_text_box(latest_msg)

    def receive_partial_transcript(self, message: str):
        # Update visual transcript
        logger.debug(f'Partial transcript: {message}')
        self.store_transcript(message)

    def receive_committed_transcript(self, message: str):
        # Update visual transcript and send non-empty messages to agent
        self.store_transcript(message)
        logger.debug(f'Committed transcript: {message}')
        if len(message) > 0:
            audio_inference_handler.on_new_messages([message])

    def store_transcript(self, message: str):
        self.transcripts_for_ui.append(message)
        self._transcript_received.set()

    async def audio_stopped_loop(self):
        # Manually flush audio buffer when user stops audio input
        while True:
            await event_manager.audio_stopped.wait()
            event_manager.audio_stopped.clear()

            if len(self.audio_chunks_buffer) > 0:
                self.process_buffer()
            asyncio.create_task(audio_transcriber.manual_commit())

class BridgeSocketHandler(BaseSocketHandler):
    """Handler for frontend-backend bridge WebSocket connections"""
    def __init__(self):
        super().__init__(SocketNames.BRIDGE)

    async def start_loop(self, websocket: WebSocket):
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('type')
            match msg_type:
                case 'state_response':
                    self.handle_state_response(data)
                case 'audio_stopped':
                    event_manager.audio_stopped.set()
                case 'config_update':
                    self.handle_config_update(data)
                case _:
                    logger.warning(f'[Bridge] Unknown message type: {msg_type}')

    def handle_state_response(self, data: dict):
        # This is a response to a tool command - resolve the pending future
        request_id = data.get('requestId')
        if request_id:
            logger.debug(f"[Bridge] Received response for requestId: {request_id}")
            socket_manager.resolve_response(request_id, data)
        else:
            logger.warning(f"[Bridge] Received state_response without requestId")

    def handle_config_update(self, data: dict):
        # Handle configuration updates from frontend
        frontend_config = data.get('data', {})
        try:
            user_config_manager.set_config(frontend_config)
            logger.info(f"[Bridge] Configuration updated: {user_config_manager.get_config()}")
        except Exception as e:
            logger.error(f"Could not update user config: {e}")
            logger.debug(f"Received config: {frontend_config}")
