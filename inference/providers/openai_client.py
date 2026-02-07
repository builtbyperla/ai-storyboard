from openai import AsyncOpenAI
from core.app_config import TokenKeys

openai_client = AsyncOpenAI(api_key=TokenKeys.OPENAI_API_KEY)