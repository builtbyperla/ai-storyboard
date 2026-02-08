# AI Storyboard App

An AI-powered storyboard creation application that combines visual generation, audio input, and intelligent canvas management.

## Prerequisites

- **Python 3**
- **Node.js**
- **API Keys**:
  - **Anthropic Claude** (core agent text inference) - Get from [Anthropic Console](https://console.anthropic.com/)
  - **OpenAI** (memory summarization + embeddings) - Get from [OpenAI API Keys](https://platform.openai.com/api-keys)
  - **ElevenLabs** (speech-to-text) - Get from [ElevenLabs API](https://elevenlabs.io/app/api-keys)
  - **Replicate** (image generation) - Get from [Replicate Platform](https://replicate.com/docs/topics/security/api-tokens)

**Important**: Be mindful of very low rate limits for some service tiers. Throttling may occur during rapid iteration.

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-storyboard
```

### 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the example configuration
cp .env.example .env

# Edit .env and add your API keys
nano .env  # Or use your preferred editor
```

### 5. Set Up Frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

### 6. Run the app

Start the backend:

```bash
source venv/bin/activate
python app.py
```

Open your browser and enter this in place of the URL to open the app:
```
http://localhost:8000/
```
## Usage

How it works (high level):
- Speak or type your input into the app and the agent will proactively generate images for ideas
  being discussed or make changes to the storyboard per your requests.
- Audio mode is triggered by clicking on the 'Start Audio' button at the bottom. Leave the audio
  running and inference will automatically be triggered by pauses in speech.
  Text input is made available by clicking the chat icon near the minimap. 
- User settings are available in the settings panel accessible by the icon at the top-left of screen.
  Here you can change the audio behavior mode (single user vs collaborative settings), the default image generation style, and the voice activity detection behavior.
- In multi-user mode, use the keyword "Atlas" for targeted requests.

Common things you can ask the agent:
- Create, add, or refine scene descriptions and frame text.
- Generate or regenerate images and request variations (different styles or compositions).
- Move, edit, or delete cards on the canvas.
- Add images to the preview pane and place them onto canvas cards.
- Focus the viewport on specific cards or ask for simple layout adjustments.
- General queries for potential ideas, information about the storyboard, etc.

## Out-of-scope
- Undo operations
- Cancellation operations
- Export or save operations

## Project Structure (Key Components)

```
ai-storyboard/
├── agent_tools/                  # MCP tool interfaces
├── common/                       # Shared models and enums
├── core/
│   ├── app_config.py             # Some hard-coded application configs
│   ├── db_core.py                # Database core (SQLite)
│   ├── vector_db.py              # Vector database interface
│   ├── memory_worker.py          # Long-term memory worker task
│   ├── embedding_worker.py       # Embedding worker task
│   ├── websocket_manager.py      # WebSocket connection manager
├── db_ops/                       # Database methods for agent, app, & recall layers
├── handlers/                     # Implementations for MCP tools + larger components
│   ├── image_generation.py
│   ├── semantic_search.py
│   └── user_interface.py
├── inference/
│   ├── agent_orchestrator.py     # Agent coordination
│   ├── agent_inference_engine.py # Core agent inference engine
│   ├── prompt_builder.py         # Agent prompt construction
│   ├── speech2text.py            # Audio transcription
│   ├── internal_event_handler.py # Internal app event handler (image completions)
│   ├── user_event_handlers.py    # User event handler (chat or audio transcripts)
│   └── providers/                # LLM provider clients
├── frontend/                     # React frontend
├── app.py                        # FastAPI application entry point
├── socket_handlers.py            # WebSocket message handlers (audio, chat, bridge)    
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment template
```

**User event flow (backend)**:
- socket_handlers.py → user_event_handlers.py → agent_orchestrator.py → agent_inference_engine.py

**Tool usage flow**:
- FastMCP client → interfaces under agent_tools/ → implementations in handlers/

**Background tasks**:
- Long-term memory summarization at periodic intervals
  - see memory_worker.py and memory_summary_engine.py
- Embedding generation and updates post-inference
  - see embedding_worker.py and embedding_engine.py

## Configuration

For more details on the agent's behavior, refer to the system prompt in [prompt_builder.py](inference/prompt_builder.py) and the tool interfaces under [agent_tools](agent_tools/).

For audio configuration settings, see [speech2text.py](inference/speech2text.py) and [pcm-processor.js](frontend/src/pcm-processor.js)

For image generation settings, see [image_generation.py](handlers/image_generation.py)

For user settings visible in the frontend, the options are defined in [user_config_definitions.py](core/user_config_definitions.py)

Some hard-coded settings such as token allowances were also defined under [app_config.py](core/app_config.py)