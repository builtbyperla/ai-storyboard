from pydantic import BaseModel, Field
import json
from typing import Optional

class ImageRequest(BaseModel):
    prompt: str = Field(description="Text description of image to generate")
    style: str = Field(description="Image style to use for image generation")
    label: str = Field(description="Human-readable label such as intro_scene or puppy_jumping")

class ToolResult(BaseModel):
    tool_name: str = Field(description="Tool that was called")
    tool_use_id: str = Field(description="Tool use ID to send back to Claude")
    is_error: bool = Field(description="Whether the tool call failed or not")
    result: Optional[object] = Field(description="Tool result object, all of these should JSON-compatible for now")
    tool_input: Optional[dict] = Field(default=None, description="Tool input parameters (for recall context)")

    def deserialize_result(self):
        return json.dumps(self.result)