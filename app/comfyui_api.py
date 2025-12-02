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

    def get_progress(self, prompt_id: str = None) -> dict:
        """Get current execution progress from ComfyUI.
        
        Args:
            prompt_id: Optional prompt ID to check progress for
        
        Returns:
            Dictionary with progress info including:
            - value: current step
            - max: total steps
            - percent: calculated percentage (0-100)
            - node: current node being executed
        """
        try:
            # Try the queue endpoint to get execution info
            response = requests.get(f"{self.server_url}/queue", timeout=10)
            if response.status_code == 200:
                data = response.json()
                queue_running = data.get("queue_running", [])
                
                # Check if our prompt is running
                for item in queue_running:
                    if len(item) >= 3:
                        running_prompt_id = item[1] if len(item) > 1 else None
                        if prompt_id is None or running_prompt_id == prompt_id:
                            # Get progress from the execution info
                            exec_info = item[2] if len(item) > 2 else {}
                            if isinstance(exec_info, dict):
                                return {
                                    "value": exec_info.get("value", 0),
                                    "max": exec_info.get("max", 1),
                                    "percent": (exec_info.get("value", 0) / max(exec_info.get("max", 1), 1)) * 100,
                                    "node": exec_info.get("node", ""),
                                    "running": True
                                }
                
                # Check queue_pending
                queue_pending = data.get("queue_pending", [])
                for item in queue_pending:
                    if len(item) >= 2:
                        pending_prompt_id = item[1] if len(item) > 1 else None
                        if prompt_id is None or pending_prompt_id == prompt_id:
                            return {"value": 0, "max": 1, "percent": 0, "node": "", "pending": True}
                
                return {"value": 0, "max": 1, "percent": 0, "node": "", "idle": True}
        except Exception:
            pass
        return {"value": 0, "max": 1, "percent": 0, "node": ""}

    def wait_for_completion(
        self,
        prompt_id: str,
        debug_dir: str = None
    ) -> tuple[bool, str, dict]:
        """Wait for a prompt to complete execution.
        
        Args:
            prompt_id: The prompt ID to wait for
            debug_dir: Optional directory to write debug logs
            
        Returns:
            Tuple of (success, message, output_data)
        """
        attempts = 0
        last_history = None
        
        while attempts < MAX_POLL_ATTEMPTS:
            success, history = self.get_history(prompt_id)
            
            if success and prompt_id in history:
                prompt_history = history[prompt_id]
                last_history = prompt_history
                
                # Check if execution is complete
                if "outputs" in prompt_history:
                    outputs = prompt_history["outputs"]
                    
                    # Debug: Write the full history to a file
                    if debug_dir:
                        self._write_debug_log(debug_dir, prompt_id, prompt_history, "success")
                    
                    return True, "Generation complete", outputs
                    
                # Check for errors
                if "status" in prompt_history:
                    status = prompt_history["status"]
                    status_str = status.get("status_str", "")
                    
                    if status_str == "error":
                        error_msg = status.get("messages", [])
                        # Debug: Write error history
                        if debug_dir:
                            self._write_debug_log(debug_dir, prompt_id, prompt_history, "error")
                        return False, f"Generation failed: {error_msg}", {}
            
            time.sleep(POLL_INTERVAL_SECONDS)
            attempts += 1
        
        # Timeout - write debug log if we have any history
        if debug_dir and last_history:
            self._write_debug_log(debug_dir, prompt_id, last_history, "timeout")
        
        return False, "Generation timed out", {}
    
    def _write_debug_log(self, debug_dir: str, prompt_id: str, history: dict, status: str):
        """Write debug log to file."""
        try:
            import os
            os.makedirs(debug_dir, exist_ok=True)
            debug_path = os.path.join(debug_dir, f"debug_history_{prompt_id}_{status}.json")
            with open(debug_path, "w") as f:
                json.dump(history, f, indent=2, default=str)
        except Exception as e:
            pass  # Ignore debug logging errors
    
    def poll_once(self, prompt_id: str) -> tuple[str, float, dict, dict]:
        """Poll for completion once and return status with detailed progress.
        
        Returns:
            Tuple of (status, progress, outputs_or_empty, progress_info)
            status: "pending", "running", "complete", "error"
            progress: 0.0 to 1.0
            outputs: dict of outputs if complete, empty dict otherwise
            progress_info: dict with detailed progress (value, max, percent, node)
        """
        success, history = self.get_history(prompt_id)
        
        # Get detailed progress info
        progress_info = self.get_progress(prompt_id)
        
        if not success or prompt_id not in history:
            # Check queue status
            if progress_info.get("pending"):
                return "pending", 0.0, {}, progress_info
            elif progress_info.get("running"):
                percent = progress_info.get("percent", 10) / 100.0
                return "running", percent, {}, progress_info
            
            pending, running = self.get_queue_status()
            if running > 0:
                return "running", 0.1, {}, progress_info
            elif pending > 0:
                return "pending", 0.0, {}, progress_info
            return "pending", 0.0, {}, progress_info
        
        prompt_history = history[prompt_id]
        
        # Check if complete
        if "outputs" in prompt_history:
            return "complete", 1.0, prompt_history["outputs"], {"percent": 100, "value": 1, "max": 1}
        
        # Check for errors
        if "status" in prompt_history:
            status = prompt_history["status"]
            if status.get("status_str") == "error":
                return "error", 0.0, {"error": status.get("messages", [])}, progress_info
        
        # Still running - use actual progress if available
        percent = progress_info.get("percent", 50) / 100.0
        return "running", percent, {}, progress_info

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
        image_path,
        subfolder: str = "",
        overwrite: bool = True
    ) -> tuple[bool, str, str]:
        """Upload an image to the ComfyUI server.
        
        Args:
            image_path: Path to the image file (can be Path or str)
            subfolder: Subfolder to upload to
            overwrite: Whether to overwrite existing files
            
        Returns:
            Tuple of (success, message, uploaded_filename)
        """
        try:
            # Ensure image_path is a Path object
            image_path = Path(image_path)
            
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

    def cancel_prompt(self, prompt_id: str) -> tuple[bool, str]:
        """Cancel/delete a prompt from the ComfyUI queue.
        
        Args:
            prompt_id: The prompt ID to cancel
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # ComfyUI uses POST to /queue with delete key to remove items
            response = requests.post(
                f"{self.server_url}/queue",
                json={"delete": [prompt_id]},
                timeout=10
            )
            if response.status_code == 200:
                return True, "Prompt cancelled successfully"
            return False, f"Failed to cancel: {response.text}"
        except Exception as e:
            return False, f"Error cancelling prompt: {str(e)}"
    
    def interrupt_generation(self) -> tuple[bool, str]:
        """Interrupt the currently running generation.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            response = requests.post(
                f"{self.server_url}/interrupt",
                timeout=10
            )
            if response.status_code == 200:
                return True, "Generation interrupted"
            return False, f"Failed to interrupt: {response.text}"
        except Exception as e:
            return False, f"Error interrupting: {str(e)}"

    def get_loras(self) -> list[str]:
        """Get list of available LoRA models from ComfyUI.
        
        Queries the /object_info endpoint to get available LoRAs
        from the LoraLoaderModelOnly node.
        
        Returns:
            List of LoRA filenames available on the server
        """
        try:
            response = requests.get(f"{self.server_url}/object_info/LoraLoaderModelOnly", timeout=30)
            if response.status_code == 200:
                data = response.json()
                # Navigate to the lora_name input options
                lora_loader = data.get("LoraLoaderModelOnly", {})
                input_info = lora_loader.get("input", {})
                required = input_info.get("required", {})
                lora_name_info = required.get("lora_name", [])
                
                # The first element should be the list of available LoRAs
                if lora_name_info and len(lora_name_info) > 0:
                    lora_list = lora_name_info[0]
                    if isinstance(lora_list, list):
                        return lora_list
            
            # Fallback: try the generic object_info endpoint
            response = requests.get(f"{self.server_url}/object_info", timeout=30)
            if response.status_code == 200:
                data = response.json()
                lora_loader = data.get("LoraLoaderModelOnly", {})
                input_info = lora_loader.get("input", {})
                required = input_info.get("required", {})
                lora_name_info = required.get("lora_name", [])
                
                if lora_name_info and len(lora_name_info) > 0:
                    lora_list = lora_name_info[0]
                    if isinstance(lora_list, list):
                        return lora_list
            
            return []
        except Exception as e:
            return []
