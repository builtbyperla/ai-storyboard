from enum import Enum
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class InputSourceType:
    AUDIO = 'audio_transcript'
    CHAT = 'chat_message'
    APP_EVENT = 'internal_app_event'