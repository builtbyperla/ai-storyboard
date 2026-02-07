from anthropic import AsyncAnthropic
from core.app_config import TokenKeys

anthropic_client = AsyncAnthropic(api_key=TokenKeys.ANTHROPIC_API_KEY)
