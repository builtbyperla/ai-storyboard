import asyncio
import httpx
import json
from pathlib import Path
from core.app_config import ImageConfig, TokenKeys
from db_ops.app import AppDB
from core.unique_id_manager import id_manager
from common.models import ImageRequest
from common.enums import RequestStatus
from core.utils.time_utils import get_current_timestamp
from core.logger_config import logger
from core.event_manager import event_manager

VLM_PROMPT = '''{{
"image_style" : "{style}",
"content_to_depict": "{content}"
}}
'''

class ImageGenerationService:
    '''
        Makes requests to flux model on Replicate to generate images with Flux.schnell
    '''
    def __init__(self):
        self.api_key = TokenKeys.REPLICATE_API_KEY
        self.model_name = ImageConfig.IMAGE_MODEL

    async def generate_image(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("REPLICATE_API_KEY not set in environment variables")

        input = {
            "prompt": prompt,
            "go_fast": True,
            "aspect_ratio": "1:1",
            "output_format": "png",
            "output_quality": 75,
            "output_megapixels": "0.25",
            "num_inference_steps": 4
        }

        headers = {
            'Authorization': f'Token {self.api_key}',
            'Content-Type': 'application/json',
            'Prefer': 'wait'
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"https://api.replicate.com/v1/models/black-forest-labs/flux-2-klein-9b/predictions",
                json={"input": input},
                headers=headers
            )

            if response.status_code != 201:
                raise Exception(f"Replicate API request failed: {response.text}")

            result = response.json()
            
            if result["status"] == "succeeded":
                return result["output"][0]
            
            if result["status"] == "failed":
                raise Exception(f"Generation failed: {result.get('error')}")
            
            raise Exception(f"Unexpected status: {result['status']}")

class ImageGenerationOrchestrator:
    def __init__(self):
        self.image_service = ImageGenerationService()
        self.batches = {}
        self.id_to_batch = {}
        self.batch_num = 0

    @staticmethod
    def _sanitize_name(name: str) -> str:
        # Make local label for images safe to use
        sanitized_name = name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        sanitized_name = ''.join(c for c in sanitized_name if c.isalnum() or c in '_-')
        return sanitized_name

    def start_batch(self):
        # Start keeping track of image requests for a full user-agent turn
        if self.batch_num in self.batches:
            self.batch_num += 1
    
    def _add_to_batch(self, task_id: str):
        # Add a task id to the current turn batch (for event trigger purposes)
        if self.batch_num not in self.batches:
            self.batches[self.batch_num] = set()

        self.id_to_batch[task_id] = self.batch_num
        self.batches[self.batch_num].add(task_id)

    async def request_image(self, request: ImageRequest) -> str:
        # Get task ID and add to history
        task_id = id_manager.get_image_request_id()
        self._add_to_batch(task_id)

        # Store image generation request and start image generation in a new task
        timestamp = get_current_timestamp()

        # Save request to DB
        request_str = json.dumps(request.model_dump())
        await AppDB.insert_image_request(
            task_id, RequestStatus.PENDING.value, timestamp, request_str
        )

        # Start image generation task (non-blocking within this method)
        asyncio.create_task(self._request_image(task_id, request))

        return task_id

    async def _request_image(self, task_id: str, request: ImageRequest) -> None:
        # Prepare formatted prompt for image generation service
        kwargs = {'style': request.style, 'content': request.prompt}
        service_prompt = VLM_PROMPT.format(**kwargs)

        # Store results or report failure
        try:
            # Call image service to generate image and return its URL
            image_url = await self.image_service.generate_image(service_prompt)

            # Create a unique image_id
            safe_label = self._sanitize_name(request.label)
            image_id = f'{safe_label}_{task_id}'

            # Store the image on disk
            local_path = await self._store_image(
                image_url,
                image_id
            )

            # Update the image cache table in DB
            timestamp = get_current_timestamp()
            await AppDB.insert_image_cache(image_id, local_path, request.prompt,
                                                        request.style, timestamp)

            # Update request table in DB
            await AppDB.update_image_request(
                task_id, RequestStatus.COMPLETED.value, image_id
            )

            logger.info(f'Successful image completion of {task_id}: {image_id}')

        except Exception as e:
            # Update request table in DB
            await AppDB.update_image_request(
                task_id, RequestStatus.FAILED.value, None
            )
            logger.error(f'Image generation request failed: {e}, request: {request}')
        finally:
            # Trigger inference if all pending images from batch are complete
            if self._update_batch(task_id):
                event_manager.image_batch_completed.set()

    async def _store_image(self, image_url: str, image_id: str) -> str:
        """
        Download image from URL and save to local disk
        Returns the local file path
        """
        # Create images directory if it doesn't exist
        filepath = Path(ImageConfig.IMAGE_CACHE_DIR, f"{image_id}.png")

        # Download and save the image
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)

            if response.status_code != 200:
                raise Exception(f"Failed to download image: {response.status_code}")

            image_data = response.content
            filepath.write_bytes(image_data)

        return str(filepath)

    def _update_batch(self, task_id: int) -> bool:
        # Remove the task ID from it's image batch and clean up
        # the batch if it's empty (all images completed)
        batch = self.id_to_batch.get(task_id)
        if batch in self.batches and task_id in self.batches[batch]:
            self.batches[batch].remove(task_id)
            if len(self.batches[batch]) == 0:
                del self.batches[batch]
                del self.id_to_batch[task_id]
                return True
        return False

image_orchestrator = ImageGenerationOrchestrator()
