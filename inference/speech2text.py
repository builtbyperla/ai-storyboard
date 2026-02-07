import asyncio
import base64
import json
import time
from typing import Callable, Optional
from urllib.parse import urlencode
import websockets
from core.app_config import TokenKeys
from core.event_manager import event_manager
from core.user_config_manager import user_config_manager
from core.logger_config import logger

class AudioTranscriber:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.ws = None
        self.api_key = TokenKeys.ELEVENLABS_API_KEY

        # VAD configuration
        self.base_vad_config = {
            "model_id": "scribe_v2_realtime",
            "language_code": "en",
            "audio_format": "pcm_16000",
            "commit_strategy": "vad",
            "tag_audio_events": False,  # Set to False to ignore laughter/background tags
            "stability": 0.8,
        }
        self.subtype_vad_config = {
            'low' : {
                "vad_silence_threshold_secs": 2,  # Longer breaks before commit
                "vad_threshold": 0.9,  # Moderate threshold to detect normal speech
                "min_speech_duration_ms": 600,
                "min_silence_duration_ms": 600,
            },
            'medium': {
                "vad_silence_threshold_secs": 1.25,  # Balanced
                "vad_threshold": 0.9,  # High threshold
                "min_speech_duration_ms": 400,  # Practical minimum for short words
                "min_silence_duration_ms": 400,  # Balanced silence
            },
            'high': {
                "vad_silence_threshold_secs": 0.75,  # Short breaks - quick commits
                "vad_threshold": 0.75,  # Balanced threshold
                "min_speech_duration_ms": 200,  # Still practical minimum for quick responses
                "min_silence_duration_ms": 200,  # Short silence detection
            }
        }

        self.base_url = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
        self.url_append = None
        self._receive_task = None
        self._ping_task = None
        self._config_task = None

        # Set default sensitivity from user config
        self._set_sensitivity(user_config_manager.get_audio_sensitivity())

        # Callbacks
        self.on_partial_transcript: Optional[Callable[[str], None]] = None
        self.on_committed_transcript: Optional[Callable[[str], None]] = None

        self._initialized = True

    async def connect(self,
                     on_partial: Optional[Callable[[str], None]] = None,
                     on_committed: Optional[Callable[[str], None]] = None):
        """Establish WebSocket connection to ElevenLabs

        Args:
            on_partial: Callback for partial transcripts (real-time updates)
            on_committed: Callback for committed transcripts (finalized segments)
        """
        if self.ws is not None:
            return

        # Set callbacks
        self.on_partial_transcript = on_partial
        self.on_committed_transcript = on_committed

        # Build URL with query parameters
        url = f"{self.base_url}?{self.url_append}"
        headers = {"xi-api-key": self.api_key}

        # Connect with ping/pong enabled (20 second interval, 60 second timeout)
        self.ws = await websockets.connect(
            url,
            additional_headers=headers,
            ping_interval=20,  # Send ping every 20 seconds
            ping_timeout=60    # Wait up to 60 seconds for pong
        )

        # Wait for session_started message
        session_msg = await self.ws.recv()
        logger.info(f"ElevenLabs session started: {session_msg}")

        # Start background task to receive user config updates
        self._config_task = asyncio.create_task(self._config_loop())

        # Start background task to receive transcripts
        self._receive_task = asyncio.create_task(self._receive_transcripts())

    async def _config_loop(self):
        while True:
            await event_manager.user_config_changed.wait()
            event_manager.user_config_changed.clear()
            mode = user_config_manager.get_audio_sensitivity()
            self._set_sensitivity(mode)

    def _set_sensitivity(self, mode: str):
        # Update audio sensitivity to the given profile by encoding
        # the new endpoint URL
        config = self.base_vad_config.copy()
        config.update(self.subtype_vad_config[mode])
        self.url_append = urlencode(config)

    def _is_connection_closed(self) -> bool:
        """Check if WebSocket connection is closed (handles different websockets versions)"""
        if not self.ws:
            return True

        # Check multiple attributes for compatibility across websockets versions
        if getattr(self.ws, 'closed', False):
            return True
        if getattr(self.ws, 'close_code', None) is not None:
            return True
        if hasattr(self.ws, 'state') and self.ws.state > 1:  # CLOSING or CLOSED
            return True

        return False

    async def _reconnect(self):
        """Reconnect to ElevenLabs after connection loss"""
        logger.warning("ElevenLabs WebSocket disconnected, attempting to reconnect...")
        await self.close()  # Clean up old connection

        # Reconnect with existing callbacks
        await self.connect(self.on_partial_transcript, self.on_committed_transcript)

        if self._is_connection_closed():
            raise RuntimeError("Failed to reconnect to ElevenLabs")

        logger.info("Successfully reconnected to ElevenLabs")

    async def _receive_transcripts(self):
        """Background task to receive and process transcripts"""
        try:
            while self.ws:
                message = await self.ws.recv()
                data = json.loads(message)

                if data["message_type"] == "partial_transcript":
                    text = data.get("text", "")
                    if len(text) > 0 and self.on_partial_transcript:
                        self.on_partial_transcript(text)

                elif data["message_type"] == "committed_transcript":
                    text = data.get("text", "")
                    if len(text) > 0 and self.on_committed_transcript:
                        self.on_committed_transcript(text)

                elif data["message_type"] == "input_error":
                    logger.error(f"ElevenLabs transcription error: {data}")

                elif data["message_type"] == "auth_error":
                    logger.error(f"ElevenLabs auth error: {data}")

                elif data["message_type"] == "quota_exceeded_error":
                    logger.error(f"ElevenLabs quota exceeded: {data}")

                elif data["message_type"] == "resource_exhausted":
                    logger.error(f"ElevenLabs resource exhausted: {data}")
                    raise RuntimeError(f"ElevenLabs at capacity: {data.get('error')}")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error receiving transcripts: {e}")

    async def send_chunk(self, pcm_chunk: bytes):
        """Send a PCM audio chunk to ElevenLabs

        Args:
            pcm_chunk: PCM audio bytes (0.2s at 16kHz = 6400 bytes)

        Note: WebSocket ping/pong keeps connection alive during silence
        """
        # Check connection health and reconnect if needed
        if self._is_connection_closed():
            await self._reconnect()

        audio_base64 = base64.b64encode(pcm_chunk).decode()

        message = {
            "message_type": "input_audio_chunk",
            "audio_base_64": audio_base64,
            "commit": False,  # VAD handles commits automatically
            "sample_rate": 16000,
        }

        await self.ws.send(json.dumps(message))

    async def manual_commit(self):
        """Manually trigger a commit when audio stops

        Sends an empty audio chunk with commit=True to force ElevenLabs
        to finalize the current segment without waiting for VAD silence detection.
        """
        # Check connection health and reconnect if needed
        if self._is_connection_closed():
            await self._reconnect()

        message = {
            "message_type": "input_audio_chunk",
            "audio_base_64": "",
            "commit": True,
            "sample_rate": 16000,
        }

        await self.ws.send(json.dumps(message))

    async def close(self):
        """Close the WebSocket connection"""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        if self.ws:
            await self.ws.close()
            self.ws = None

audio_transcriber = AudioTranscriber()