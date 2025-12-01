"""Configuration settings for the Wan2.2 Video Generator app."""

# ComfyUI Server Configuration
COMFYUI_SERVER_URL = "http://3090.zero:8188"

# Default Generation Parameters
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 640
DEFAULT_FPS = 16
DEFAULT_FRAMES_PER_SEGMENT = 81  # 5 seconds at 16 FPS

# Model Names
MODELS = {
    "high_noise": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    "low_noise": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
    "vae": "wan_2.1_vae.safetensors",
    "text_encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
}

# Generation Parameters (Two-Pass Sampling)
GENERATION_PARAMS = {
    "first_pass": {
        "steps": 20,
        "cfg": 3.5,
        "sampler_name": "euler",
        "scheduler": "simple",
        "start_at_step": 0,
        "end_at_step": 10,
        "add_noise": "enable",
        "return_with_leftover_noise": "enable",
    },
    "second_pass": {
        "steps": 20,
        "cfg": 3.5,
        "sampler_name": "euler",
        "scheduler": "simple",
        "start_at_step": 10,
        "end_at_step": 10000,
        "add_noise": "disable",
        "return_with_leftover_noise": "disable",
    },
    "model_sampling_shift": 8.0,
}

# Negative Prompt (from reference workflow)
DEFAULT_NEGATIVE_PROMPT = (
    "blurry, low quality, distorted, deformed, ugly, bad anatomy, watermark, text, logo, "
    "static, frozen, jerky motion, artifacts, noise, overexposed, underexposed"
)

# Output Directories
OUTPUT_DIR = "output"
SEGMENTS_DIR = "segments"
FRAMES_DIR = "frames"

# Segment Duration Options (frames at 16 FPS)
SEGMENT_DURATIONS = {
    "3 seconds": 49,
    "4 seconds": 65,
    "5 seconds": 81,
}

# Polling Configuration
POLL_INTERVAL_SECONDS = 2
MAX_POLL_ATTEMPTS = 600  # 20 minutes max wait time
