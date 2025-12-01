"""ComfyUI API client for interacting with the remote ComfyUI server."""

import json
import time
import requests
from pathlib import Path
from typing import Optional
from config import COMFYUI_SERVER_URL, POLL_INTERVAL_SECONDS, MAX_POLL_ATTEMPTS


class ComfyUIClient:
    """Client for interacting with ComfyUI's REST API."""

    def __init__(self, server_url: str = COMFYUI_SERVER_URL):
        self.server_url = server_url.rstrip("/")

    def check_connection(self) -> tuple[bool, str]:
        """Check if the ComfyUI server is reachable.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            response = requests.get(f"{self.server_url}/system_stats", timeout=10)
            if response.status_code == 200:
                return True, "Connected to ComfyUI server"
            return False, f"Server returned status code: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, f"Cannot connect to ComfyUI server at {self.server_url}"
        except requests.exceptions.Timeout:
            return False, "Connection to ComfyUI server timed out"
        except Exception as e:
            return False, f"Error connecting to ComfyUI server: {str(e)}"

    def queue_prompt(self, workflow: dict) -> tuple[bool, str, Optional[str]]:
        """Queue a workflow prompt for execution.
        
        Args:
            workflow: The workflow JSON to execute
            
        Returns:
            Tuple of (success, message, prompt_id)
        """
        try:
            payload = {"prompt": workflow}
            response = requests.post(
                f"{self.server_url}/prompt",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                prompt_id = result.get("prompt_id")
                if prompt_id:
                    return True, "Prompt queued successfully", prompt_id
                return False, "No prompt_id in response", None
            else:
                error_msg = response.text
                return False, f"Failed to queue prompt: {error_msg}", None
                
        except requests.exceptions.RequestException as e:
            return False, f"Request error: {str(e)}", None
        except Exception as e:
            return False, f"Error queuing prompt: {str(e)}", None

    def get_history(self, prompt_id: str) -> tuple[bool, dict]:
        """Get the execution history for a prompt.
        
        Args:
            prompt_id: The prompt ID to check
            
        Returns:
            Tuple of (success, history_data)
        """
        try:
            response = requests.get(
                f"{self.server_url}/history/{prompt_id}",
                timeout=30
            )
            
            if response.status_code == 200:
                return True, response.json()
            return False, {}
            
        except Exception as e:
            return False, {}

    def wait_for_completion(
        self,
        prompt_id: str,
        progress_callback=None
    ) -> tuple[bool, str, dict]:
        """Wait for a prompt to complete execution.
        
        Args:
            prompt_id: The prompt ID to wait for
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Tuple of (success, message, output_data)
        """
        attempts = 0
        
        while attempts < MAX_POLL_ATTEMPTS:
            success, history = self.get_history(prompt_id)
            
            if success and prompt_id in history:
                prompt_history = history[prompt_id]
                
                # Check if execution is complete
                if "outputs" in prompt_history:
                    outputs = prompt_history["outputs"]
                    return True, "Generation complete", outputs
                    
                # Check for errors
                if "status" in prompt_history:
                    status = prompt_history["status"]
                    if status.get("status_str") == "error":
                        error_msg = status.get("messages", [])
                        return False, f"Generation failed: {error_msg}", {}
            
            # Update progress if callback provided
            if progress_callback:
                progress_callback(attempts, MAX_POLL_ATTEMPTS)
            
            time.sleep(POLL_INTERVAL_SECONDS)
            attempts += 1
        
        return False, "Generation timed out", {}

    def download_output(
        self,
        filename: str,
        subfolder: str = "",
        output_type: str = "output"
    ) -> tuple[bool, bytes]:
        """Download an output file from the server.
        
        Args:
            filename: Name of the file to download
            subfolder: Subfolder where the file is located
            output_type: Type of output (output, input, temp)
            
        Returns:
            Tuple of (success, file_data)
        """
        try:
            params = {
                "filename": filename,
                "type": output_type
            }
            if subfolder:
                params["subfolder"] = subfolder
                
            response = requests.get(
                f"{self.server_url}/view",
                params=params,
                timeout=120
            )
            
            if response.status_code == 200:
                return True, response.content
            return False, b""
            
        except Exception as e:
            return False, b""

    def upload_image(
        self,
        image_path: Path,
        subfolder: str = "",
        overwrite: bool = True
    ) -> tuple[bool, str, str]:
        """Upload an image to the ComfyUI server.
        
        Args:
            image_path: Path to the image file
            subfolder: Subfolder to upload to
            overwrite: Whether to overwrite existing files
            
        Returns:
            Tuple of (success, message, uploaded_filename)
        """
        try:
            with open(image_path, "rb") as f:
                files = {
                    "image": (image_path.name, f, "image/png")
                }
                data = {
                    "overwrite": str(overwrite).lower()
                }
                if subfolder:
                    data["subfolder"] = subfolder
                    
                response = requests.post(
                    f"{self.server_url}/upload/image",
                    files=files,
                    data=data,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    uploaded_name = result.get("name", image_path.name)
                    return True, "Image uploaded successfully", uploaded_name
                return False, f"Upload failed: {response.text}", ""
                
        except Exception as e:
            return False, f"Error uploading image: {str(e)}", ""

    def get_queue_status(self) -> tuple[int, int]:
        """Get the current queue status.
        
        Returns:
            Tuple of (queue_remaining, queue_running)
        """
        try:
            response = requests.get(f"{self.server_url}/queue", timeout=10)
            if response.status_code == 200:
                data = response.json()
                queue_running = len(data.get("queue_running", []))
                queue_pending = len(data.get("queue_pending", []))
                return queue_pending, queue_running
            return 0, 0
        except Exception:
            return 0, 0
