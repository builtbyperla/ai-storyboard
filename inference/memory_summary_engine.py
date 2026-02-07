from db_ops.app import AppDB
from core.app_config import MemoryConfig, TokenKeys
from inference.providers.openai_client import openai_client
import json

class MemorySummaryEngine:
    """Engine for summarizing conversation history into long-term memory."""
    
    @staticmethod
    async def refresh_longterm_memory(current_memory: str, entries: list) -> str:
        """
        Update long-term memory with new recall entries.

        Args:
            current_memory: Previous long-term memory summary (or None)
            entries: List of recall entry dicts to process

        Returns:
            Updated memory summary, or None if no entries
        """
        if len(entries) == 0:
            return None

        # Format prompt with message history and last summary
        history_str = json.dumps(entries)
        previous = current_memory or "No previous summary."
        prompt = LONG_TERM_MEMORY_PROMPT.format(history=history_str, previous=previous)

        # Call inference provider with prompt to resummarize
        response = await MemorySummaryEngine.call_llm(prompt)
        return response

    @staticmethod
    async def call_llm(prompt: str) -> str:
        """
        Make a single-shot prompt call to OpenAI ChatGPT using the async SDK.
        """
        response = await openai_client.chat.completions.create(
            model=MemoryConfig.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            timeout=60.0
        )

        if not response.choices:
            raise Exception("No choices in OpenAI API response")

        content = response.choices[0].message.content
        if content is None:
            raise Exception("No content found in OpenAI API response")

        return content

LONG_TERM_MEMORY_PROMPT = '''
You are creating a brief for an AI agent about an ongoing project on an interactive storyboard.

The agent already has access to:
- Current board state (what cards exist, their content, their positions)
- Recent message history (what was just discussed)
- Semantic search over past conversation (can retrieve specific details on demand)
- What images look like and what text is on cards

Because the agent has these tools, you do NOT need to preserve fine-grained details. The agent can look up 
specific content when needed. Your job is to capture only the high-level context it can't reconstruct:
- WHY things are the way they are
- WHAT the user cares about consistently  
- KEY structural decisions and patterns
- Preferences the user asks you to remember

THINK IN LEVELS - capture decisions, not content or actions:

Content level (DON'T capture): "romantic B-plot about two characters," "warm tropical lighting," character names/descriptions
Decision level (DO capture): "user added a B-plot structure," "user wants consistent visual style across all images"

Action level (DON'T capture): "agent arranged cards in 2x2 grid," "user moved card to position X," routine grid adjustments
Preference level (DO capture): "user explicitly prefers 2x2 layouts," "user corrects spacing multiple times"

Some other notes:
Image style is a preset defined in the user settings and reflected in injected state information.
All included tool results are for agent-initiated events. No direct manipulation of the canvas is reflected
by the user actions. Keep the summary focus on conversation themes and direction, not on tooling
or agent decisions.

Ask: Is this a HIGH-LEVEL PATTERN/DECISION or a FINE-GRAINED DETAIL/ACTION?
- "User chose 3-act structure for the story" = key structural decision, capture it
- "Act 1 is about setup at beach club" = content detail the agent can see/search, skip it
- "Agent created a grid layout" = routine action, skip it  
- "User consistently requests grid layouts and corrects toward them" = clear preference, capture it
- "Character wears a red shirt" = fine detail, skip it
- "User finalized the main character design after multiple iterations" = key decision, capture it

Write 1-2 paragraphs capturing only significant decisions, structural choices, and consistent patterns. 
Skip fine details—the agent can retrieve those when needed.

CURRENT LONG-TERM MEMORY:
{previous}

RECENT MESSAGES:
{history}

Output only the updated memory. No preamble.
'''
