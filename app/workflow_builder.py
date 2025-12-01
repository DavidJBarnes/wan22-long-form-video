"""Build ComfyUI workflow JSON for Wan2.2 I2V generation."""

import random
from typing import Optional
from config import MODELS, GENERATION_PARAMS, DEFAULT_NEGATIVE_PROMPT


def build_workflow(
    positive_prompt: str,
    image_filename: str,
    width: int = 640,
    height: int = 640,
    num_frames: int = 81,
    fps: int = 16,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    output_prefix: str = "video/wan_segment",
    seed: Optional[int] = None,
    high_noise_lora: Optional[str] = None,
    low_noise_lora: Optional[str] = None
) -> dict:
    """Build a ComfyUI workflow JSON for Wan2.2 I2V generation.
    
    This creates a two-pass sampling workflow using the high_noise and low_noise models.
    Optionally applies LoRA models to each pass.
    
    Args:
        positive_prompt: The positive prompt describing the video
        image_filename: Filename of the start image (already uploaded to ComfyUI)
        width: Video width in pixels
        height: Video height in pixels
        num_frames: Number of frames to generate
        fps: Frames per second for the output video
        negative_prompt: The negative prompt
        output_prefix: Prefix for the output video filename
        seed: Random seed (if None, will be randomized)
        high_noise_lora: Optional LoRA filename to apply to high noise model
        low_noise_lora: Optional LoRA filename to apply to low noise model
        
    Returns:
        Dictionary containing the workflow JSON
    """
    if seed is None:
        seed = random.randint(0, 2**53)
    
    params = GENERATION_PARAMS
    
    # Determine model input sources for ModelSamplingSD3 nodes
    # If LoRA is used, it goes between UNETLoader and ModelSamplingSD3
    high_noise_model_source = "3"  # Default: directly from UNETLoader
    low_noise_model_source = "4"   # Default: directly from UNETLoader
    
    workflow = {
        # CLIPLoader - Text Encoder
        "1": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": MODELS["text_encoder"],
                "type": "wan",
                "device": "default"
            }
        },
        
        # VAELoader
        "2": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": MODELS["vae"]
            }
        },
        
        # UNETLoader - High Noise Model
        "3": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": MODELS["high_noise"],
                "weight_dtype": "default"
            }
        },
        
        # UNETLoader - Low Noise Model
        "4": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": MODELS["low_noise"],
                "weight_dtype": "default"
            }
        },
    }
    
    # Add LoRA nodes if specified
    if high_noise_lora:
        workflow["101"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["3", 0],
                "lora_name": high_noise_lora,
                "strength_model": 1.0
            }
        }
        high_noise_model_source = "101"
    
    if low_noise_lora:
        workflow["102"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["4", 0],
                "lora_name": low_noise_lora,
                "strength_model": 1.0
            }
        }
        low_noise_model_source = "102"
    
    # Add ModelSamplingSD3 nodes with correct model sources
    workflow["5"] = {
        # ModelSamplingSD3 - High Noise Model
        "class_type": "ModelSamplingSD3",
        "inputs": {
            "model": [high_noise_model_source, 0],
            "shift": params["model_sampling_shift"]
        }
    }
    
    workflow["6"] = {
        # ModelSamplingSD3 - Low Noise Model
        "class_type": "ModelSamplingSD3",
        "inputs": {
            "model": [low_noise_model_source, 0],
            "shift": params["model_sampling_shift"]
        }
    }
    
    # Add remaining nodes
    workflow.update({
        
        # CLIPTextEncode - Positive Prompt
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["1", 0],
                "text": positive_prompt
            }
        },
        
        # CLIPTextEncode - Negative Prompt
        "8": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["1", 0],
                "text": negative_prompt
            }
        },
        
        # LoadImage - Start Image
        "9": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_filename
            }
        },
        
        # WanImageToVideo
        "10": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["7", 0],
                "negative": ["8", 0],
                "vae": ["2", 0],
                "start_image": ["9", 0],
                "width": width,
                "height": height,
                "length": num_frames,
                "batch_size": 1
            }
        },
        
        # KSamplerAdvanced - First Pass (High Noise)
        "11": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["5", 0],
                "positive": ["10", 0],
                "negative": ["10", 1],
                "latent_image": ["10", 2],
                "add_noise": params["first_pass"]["add_noise"],
                "noise_seed": seed,
                "control_after_generate": "randomize",
                "steps": params["first_pass"]["steps"],
                "cfg": params["first_pass"]["cfg"],
                "sampler_name": params["first_pass"]["sampler_name"],
                "scheduler": params["first_pass"]["scheduler"],
                "start_at_step": params["first_pass"]["start_at_step"],
                "end_at_step": params["first_pass"]["end_at_step"],
                "return_with_leftover_noise": params["first_pass"]["return_with_leftover_noise"]
            }
        },
        
        # KSamplerAdvanced - Second Pass (Low Noise)
        "12": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["6", 0],
                "positive": ["10", 0],
                "negative": ["10", 1],
                "latent_image": ["11", 0],
                "add_noise": params["second_pass"]["add_noise"],
                "noise_seed": seed,
                "control_after_generate": "fixed",
                "steps": params["second_pass"]["steps"],
                "cfg": params["second_pass"]["cfg"],
                "sampler_name": params["second_pass"]["sampler_name"],
                "scheduler": params["second_pass"]["scheduler"],
                "start_at_step": params["second_pass"]["start_at_step"],
                "end_at_step": params["second_pass"]["end_at_step"],
                "return_with_leftover_noise": params["second_pass"]["return_with_leftover_noise"]
            }
        },
        
        # VAEDecode
        "13": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["12", 0],
                "vae": ["2", 0]
            }
        },
        
        # CreateVideo
        "14": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["13", 0],
                "fps": fps
            }
        },
        
        # SaveVideo
        "15": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["14", 0],
                "filename_prefix": output_prefix,
                "format": "auto",
                "codec": "auto"
            }
        }
    })
    
    return workflow


def calculate_stages(total_duration_seconds: int, fps: int = 16) -> list[dict]:
    """Calculate the optimal stage breakdown for a target duration.
    
    Args:
        total_duration_seconds: Target total video duration in seconds
        fps: Frames per second
        
    Returns:
        List of stage dictionaries with duration and frame count
    """
    # Prefer 5-second segments, fall back to 4 or 3 if needed for better fit
    segment_options = [
        (5, 81),  # 5 seconds at 16 FPS
        (4, 65),  # 4 seconds at 16 FPS
        (3, 49),  # 3 seconds at 16 FPS
    ]
    
    # Try to find the best fit
    best_fit = None
    best_remainder = float('inf')
    
    for duration, frames in segment_options:
        num_segments = total_duration_seconds // duration
        remainder = total_duration_seconds % duration
        
        if num_segments > 0 and remainder < best_remainder:
            best_fit = (duration, frames, num_segments, remainder)
            best_remainder = remainder
    
    if best_fit is None:
        # Default to 5-second segments
        duration, frames = 5, 81
        num_segments = max(1, total_duration_seconds // duration)
    else:
        duration, frames, num_segments, remainder = best_fit
        
        # If there's a significant remainder, add one more segment
        if remainder >= 2:
            num_segments += 1
    
    stages = []
    for i in range(num_segments):
        stages.append({
            "stage_number": i + 1,
            "duration_seconds": duration,
            "num_frames": frames
        })
    
    return stages


def estimate_generation_time(num_frames: int, num_stages: int) -> str:
    """Estimate the total generation time.
    
    Based on reference workflow timings:
    - fp8_scaled: ~536s for first generation, ~513s for subsequent (640x640, 81 frames)
    
    Args:
        num_frames: Frames per segment
        num_stages: Number of stages
        
    Returns:
        Human-readable time estimate string
    """
    # Base time for 81 frames at 640x640
    base_time_per_stage = 520  # seconds (average of 536 and 513)
    
    # Scale by frame count (rough estimate)
    time_per_stage = base_time_per_stage * (num_frames / 81)
    
    total_seconds = time_per_stage * num_stages
    
    if total_seconds < 60:
        return f"~{int(total_seconds)} seconds"
    elif total_seconds < 3600:
        minutes = int(total_seconds / 60)
        return f"~{minutes} minutes"
    else:
        hours = total_seconds / 3600
        return f"~{hours:.1f} hours"
