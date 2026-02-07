# Auto-import tool modules to register MCP tools
# This ensures decorators execute when the package is imported
from . import user_interface_tool, image_generation_tool

__all__ = ['user_interface_tool', 'image_generation_tool']
