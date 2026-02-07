from core.user_config_definitions import map_config_for_backend, IMAGE_STYLES, get_defaults
from core.event_manager import event_manager
from dataclasses import dataclass

class UserConfigManager:
    """Singleton for managing user configuration state"""
    def __init__(self):
        self._config = get_defaults()

    def set_config(self, config: dict):
        """Set the current user config (from frontend)"""
        self._config = map_config_for_backend(config)
        event_manager.user_config_changed.set()

    def get_config(self) -> dict:
        """Get the current user config, or defaults if not set"""
        if self._config is None:
            return get_defaults()
        return self._config

    def get_image_style_prompt(self) -> str:
        """Convenience method to get the image style prompt"""
        return self.get_config()['image_style_prompt']

    def get_user_mode(self) -> str:
        """Convenience method to get the user mode"""
        return self.get_config()['user_mode']

    def get_audio_sensitivity(self):
        return self.get_config()['audio_sensitivity']

    def get_agent_model(self):
        return self.get_config()['agent_model']

    def get_agent_thinking(self):
        return self.get_config()['agent_thinking']

# Global instance
user_config_manager = UserConfigManager()
