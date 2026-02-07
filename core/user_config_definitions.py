from dataclasses import dataclass
from typing import Any
from core.logger_config import logger

@dataclass(frozen=True)
class ConfigOption:
    display: str
    value: Any = None

    def __post_init__(self):
        if self.value is None:
            object.__setattr__(self, 'value', self.key)

########################################
# Config options
########################################
USER_MODES = {
    'single': ConfigOption('Single User', 'single'),
    'multi': ConfigOption('Collaborative (consensus-based)', 'multi'),
}

IMAGE_STYLES = {
'illustration_watercolor': ConfigOption(
    'Watercolor Illustration',
    'watercolor painting with soft illustrated rendering, pigment suspended in water on white paper, color bleeding beyond intended edges, darker pigment pooling along wet boundaries, visible brush stroke texture, layered translucent washes, white paper visible in highlights, loose painterly aesthetic. Render as hand-painted watercolor artwork.'
),
'sketch_refined': ConfigOption(
    'Pencil Sketch',
    'graphite pencil sketch with loose expressive strokes, visible sketchy line work, blended shading with paper texture showing through, tonal range from light gray to black, hand-drawn sketch quality. Render as artistic sketch drawing.'
),
'illustration_flat': ConfigOption(
    'Flat Vector Illustration',
    'bold flat vector illustration with solid color fills and hard edges, no shading or gradients, simplified geometric shapes, limited color palette, smooth graphic style. Render as clean graphic design artwork.'
),
'illustration_ink_hatched': ConfigOption(
    'Hatched Ink Drawing',
    'black and white pen and ink drawing with varied line weights, parallel hatching for gray tones, cross-hatching for shadows, solid black fills, high contrast monochrome style. Render as traditional hand-drawn ink artwork, black and white only.'
),
'photo_studio': ConfigOption(
    'Studio Photography',
    'photorealistic studio photograph with professional lighting, clean neutral background, sharp focus, crisp details with controlled highlights and shadows'
),
'illustration_digital_paint': ConfigOption(
    'Soft Digital Painting',
    'soft digital painting with rich saturated colors, smooth gradient shading, gentle diffuse lighting, painterly brush strokes with blended soft edges, atmospheric depth with hazy backgrounds, stylized forms, animation concept art aesthetic. Render as digital painted artwork.'
),
'custom': ConfigOption('Custom', ''),
}

AGENT_AUDIO_MODES = {
    'none': ConfigOption('None', 'none'),
    'notification': ConfigOption('Notification sound', 'notification'),
}

AUDIO_SENSITIVITY = {
    'low': ConfigOption('Low', 'low'),
    'medium': ConfigOption('Medium', 'medium'),
    'high': ConfigOption('High', 'high'),
}

AGENT_MODELS = {
    'claude-haiku-4-5': ConfigOption('Claude Haiku 4.5', 'claude-haiku-4-5'),
    'claude-sonnet-4-5': ConfigOption('Claude Sonnet 4.5', 'claude-sonnet-4-5'),
    'claude-opus-4-5': ConfigOption('Claude Opus 4.5', 'claude-opus-4-5'),
}

AGENT_THINKING = {
    'enabled': ConfigOption('Enabled', True),
    'disabled': ConfigOption('Disabled', False),
}

# Default configuration values
DEFAULT_CONFIG = {
    'user_mode': 'multi',
    'image_style': 'illustration_watercolor',
    'audio_sensitivity': 'medium',
    'agent_model': 'claude-haiku-4-5',
    'agent_thinking': 'disabled',
}

def get_display_from_options(config_dict):
    '''
     Maps the dicts defined above to use the display value from ConfigOption(s)
     so the frontend can use it.
    '''
    display_dict = {}
    for key in config_dict:
        display_dict[key] = config_dict[key].display
    return display_dict

def prepare_user_config_for_frontend():
    '''
        User config used by frontend
    '''
    config_options = {
        'userMode': {
            'options': get_display_from_options(USER_MODES),
            'default': DEFAULT_CONFIG['user_mode'],
            'tooltip': {
                'title': 'User Mode',
                'body': 'Listening mode for agent when using voice mode',
                'items': [
                    'Single User: All input treated as direct messages to agent',
                    'Collaborative: Agent listens for consensus markers in a multi-user conversation. Use the keyword "Atlas" for targeted requests to the agent.'
                ]
            }
        },
        'imageStyle': {
            'options': get_display_from_options(IMAGE_STYLES),
            'default': DEFAULT_CONFIG['image_style'],
            'tooltip': {
                'title': 'Image Style',
                'body': 'Default styling prompts provided to agent for image generation.',
                'items': []
            }
        },
        'agentAudioMode': {
            'options': get_display_from_options(AGENT_AUDIO_MODES),
            'default': 'none'
        },
        'notificationVolume': {
            'default': 0.5  # 0.0 to 1.0
        },
        'audioSensitivity': {
            'options': get_display_from_options(AUDIO_SENSITIVITY),
            'default': DEFAULT_CONFIG['audio_sensitivity'],
            'tooltip': {
                'title': 'Audio Sensitivity',
                'body': 'Speech-to-text transcripts are sent to the agent when pauses in speech are detected. This setting controls the sensitivity.',
                'items': [
                    'Low — allows for longer pauses',
                    'Medium — balanced detection',
                    'High — captures very short pauses and words'
                ]
            }
        },
        'agentModel': {
            'options': get_display_from_options(AGENT_MODELS),
            'default': DEFAULT_CONFIG['agent_model']
        },
        'agentThinking': {
            'options': get_display_from_options(AGENT_THINKING),
            'default': DEFAULT_CONFIG['agent_thinking']
        }
    }

    return config_options

def map_config_for_backend(user_config: dict):
    # Get selected options and check if they're valid
    user_mode = user_config.get('userMode')
    image_style = user_config.get('imageStyle')
    custom_image_style = user_config.get('customStylePrompt')
    audio_sensitivity = user_config.get('audioSensitivity')
    agent_model = user_config.get('agentModel')
    agent_thinking = user_config.get('agentThinking')

    if user_mode not in USER_MODES or image_style not in IMAGE_STYLES:
        raise Exception("Invalid user configuration received")

    if audio_sensitivity not in AUDIO_SENSITIVITY:
        raise Exception("Invalid audio sensitivity received")

    if agent_model not in AGENT_MODELS:
        raise Exception("Invalid agent model received")

    if agent_thinking not in AGENT_THINKING:
        raise Exception("Invalid agent thinking received")

    # Map image style to a prompt
    image_style_prompt = IMAGE_STYLES[image_style].value
    if image_style == 'custom':
        image_style_prompt = custom_image_style

    # Assemble config with snake case keys for internal
    mapped_config = {
        'user_mode' : user_mode,
        'image_style_prompt' : image_style_prompt,
        'audio_sensitivity' : audio_sensitivity,
        'agent_model' : agent_model,
        'agent_thinking' : AGENT_THINKING[agent_thinking].value
    }

    return mapped_config

USER_CONFIG_OPTIONS = prepare_user_config_for_frontend()

def get_defaults():
    '''
        Get the default user configuration in backend format
    '''
    defaults = {
        'user_mode': DEFAULT_CONFIG['user_mode'],
        'image_style_prompt': IMAGE_STYLES[DEFAULT_CONFIG['image_style']].value,
        'audio_sensitivity': DEFAULT_CONFIG['audio_sensitivity'],
        'agent_model': DEFAULT_CONFIG['agent_model'],
        'agent_thinking': AGENT_THINKING[DEFAULT_CONFIG['agent_thinking']].value
    }
    return defaults
