"""Settings page for the Wan2.2 Video Generator app."""

import streamlit as st
import json
from pathlib import Path


def save_settings(settings: dict) -> bool:
    """Save settings to file.
    
    Args:
        settings: Settings dictionary to save
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        settings_file = Path("app_settings.json")
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Failed to save settings: {e}")
        return False


def render():
    """Render the settings page."""
    st.title("Settings")
    st.caption("Configure your video generation settings")
    
    # Get current settings
    app_settings = st.session_state.get("app_settings", {})
    
    st.divider()
    
    # ComfyUI Server Configuration
    st.subheader("ComfyUI Server Configuration")
    
    comfyui_url = st.text_input(
        "ComfyUI Server URL",
        value=app_settings.get("comfyui_server_url", "http://3090.zero:8188"),
        help="The URL of your ComfyUI server"
    )
    
    st.divider()
    
    # Default Generation Parameters
    st.subheader("Default Generation Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        default_width = st.number_input(
            "Default Width",
            min_value=256,
            max_value=2048,
            value=app_settings.get("default_width", 640),
            step=64,
            help="Default video width in pixels"
        )
        
        default_fps = st.number_input(
            "Default FPS",
            min_value=8,
            max_value=60,
            value=app_settings.get("default_fps", 16),
            step=1,
            help="Default frames per second"
        )
    
    with col2:
        default_height = st.number_input(
            "Default Height",
            min_value=256,
            max_value=2048,
            value=app_settings.get("default_height", 640),
            step=64,
            help="Default video height in pixels"
        )
        
        default_frames = st.number_input(
            "Default Frames Per Segment",
            min_value=17,
            max_value=161,
            value=app_settings.get("default_frames_per_segment", 81),
            step=16,
            help="Default number of frames per segment"
        )
    
    st.divider()
    
    # Models Configuration
    st.subheader("Models Configuration")
    st.caption("Configure the model filenames used for generation (JSON format)")
    
    models_default = app_settings.get("models", {
        "high_noise": "wan2.2_i2v_high_noise_14B_fp16.safetensors",
        "low_noise": "wan2.2_i2v_low_noise_14B_fp16.safetensors",
        "vae": "wan_2.1_vae.safetensors",
        "text_encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    })
    
    models_json = st.text_area(
        "Models (JSON)",
        value=json.dumps(models_default, indent=2),
        height=150,
        help="Model filenames in JSON format"
    )
    
    # Validate JSON
    try:
        models = json.loads(models_json)
        models_valid = True
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON for Models: {e}")
        models_valid = False
        models = models_default
    
    st.divider()
    
    # Generation Parameters
    st.subheader("Generation Parameters")
    st.caption("Two-pass sampling configuration (JSON format)")
    
    gen_params_default = app_settings.get("generation_params", {
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
    })
    
    gen_params_json = st.text_area(
        "Generation Parameters (JSON)",
        value=json.dumps(gen_params_default, indent=2),
        height=300,
        help="Generation parameters for two-pass sampling"
    )
    
    # Validate JSON
    try:
        gen_params = json.loads(gen_params_json)
        gen_params_valid = True
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON for Generation Parameters: {e}")
        gen_params_valid = False
        gen_params = gen_params_default
    
    st.divider()
    
    # Default Negative Prompt
    st.subheader("Default Negative Prompt")
    
    negative_prompt_default = app_settings.get("default_negative_prompt", 
        "blurry, low quality, distorted, deformed, ugly, bad anatomy, watermark, text, logo, "
        "static, frozen, jerky motion, artifacts, noise, overexposed, underexposed"
    )
    
    negative_prompt = st.text_area(
        "Negative Prompt",
        value=negative_prompt_default,
        height=100,
        help="Default negative prompt used for all generations"
    )
    
    st.divider()
    
    # Segment Durations
    st.subheader("Segment Durations")
    st.caption("Available segment duration options (JSON format)")
    
    segment_durations_default = app_settings.get("segment_durations", {
        "3 seconds": 49,
        "4 seconds": 65,
        "5 seconds": 81,
    })
    
    segment_durations_json = st.text_area(
        "Segment Durations (JSON)",
        value=json.dumps(segment_durations_default, indent=2),
        height=100,
        help="Segment duration options with frame counts"
    )
    
    # Validate JSON
    try:
        segment_durations = json.loads(segment_durations_json)
        segment_durations_valid = True
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON for Segment Durations: {e}")
        segment_durations_valid = False
        segment_durations = segment_durations_default
    
    st.divider()
    
    # Output Directories (read-only)
    st.subheader("Output Directories")
    st.caption("These directories are fixed and cannot be changed")
    
    with st.container(border=True):
        st.markdown("**Output Directory:** `output`")
        st.markdown("**Segments Directory:** `segments`")
        st.markdown("**Frames Directory:** `frames`")
    
    st.divider()
    
    # Save button
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col2:
        if st.button("Save Settings", type="primary", use_container_width=True):
            # Check all validations
            if not models_valid:
                st.error("Cannot save: Invalid Models JSON")
            elif not gen_params_valid:
                st.error("Cannot save: Invalid Generation Parameters JSON")
            elif not segment_durations_valid:
                st.error("Cannot save: Invalid Segment Durations JSON")
            else:
                # Build settings dict
                new_settings = {
                    "comfyui_server_url": comfyui_url,
                    "default_width": default_width,
                    "default_height": default_height,
                    "default_fps": default_fps,
                    "default_frames_per_segment": default_frames,
                    "models": models,
                    "generation_params": gen_params,
                    "default_negative_prompt": negative_prompt,
                    "segment_durations": segment_durations,
                }
                
                # Save to file and session state
                if save_settings(new_settings):
                    st.session_state.app_settings = new_settings
                    st.success("Settings saved successfully!")
                    st.rerun()
