from datetime import timedelta
import os
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

# API token keys loaded from environment
class TokenKeys:
    ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', None)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', None)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)
    REPLICATE_API_KEY = os.getenv('REPLICATE_API_KEY', None)

# Application-wide configuration
class AppConfig:
    DEFAULT_TIMERANGE_TD = timedelta(minutes=5)
    DEFAULT_TIMERANGE_MS = DEFAULT_TIMERANGE_TD.total_seconds() * 1000  # 5 minutes in milliseconds
    REQUEST_STATE_WINDOW_MS = timedelta(minutes=1.5).total_seconds() * 1000

# Database configuration
class DatabaseConfig:
    DB_DIR = './session_data'
    DB_PATH = os.path.join(DB_DIR, 'app_db.db')

# Image generation configuration
class ImageConfig:
    IMAGE_MODEL = 'black-forest-labs/flux-2-klein-9b'
    IMAGE_CACHE_DIR = './session_data/images/'

class ClaudeConfig:
    AGENT_MODEL = "claude-haiku-4-5"
    AGENT_THINKING_ENABLED = False

    # Model-specific token budgets
    # Thinking budget + response space must not exceed max_tokens
    MODEL_TOKEN_CONFIG = {
        "claude-haiku-4-5": {
            "max_tokens": 4096,
            "thinking_budget_tokens": 2048,
        },
        "claude-sonnet-4-5": {
            "max_tokens": 4096,
            "thinking_budget_tokens": 2048,
        },
        "claude-opus-4-5": {
            "max_tokens": 4096,
            "thinking_budget_tokens": 2048,
        },
    }

class MemoryConfig:
    LONGTERM_MEMORY_REFRESH_SEC = int(AppConfig.DEFAULT_TIMERANGE_TD.total_seconds() / 2)
    OPENAI_TEXT_MODEL = 'gpt-5.2'

class SemanticSearchConfig:
    MIN_MEMORIES = 5
    WINDOW_MS = 10
    SIMILARITY_THRESHOLD = 0.2

class EmbeddingConfig:
    OPENAI_EMBEDDING_MODEL = 'text-embedding-3-small'
    VECTOR_DB_PATH = './session_data/vectordb.lance'
    EMBEDDING_DIMENSION = 1536  # Dimension for text-embedding-3-small