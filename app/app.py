"""Main Streamlit application with multi-page navigation."""

import streamlit as st
from pathlib import Path
import json

# Page imports
from pages import dashboard, job_queue, image_library, settings

# App configuration
st.set_page_config(
    page_title="Wan2.2 Video Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide default Streamlit pages navigation and style custom nav
st.markdown("""
<style>
    /* Hide default Streamlit pages navigation and remove gap */
    [data-testid="stSidebarNav"] {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Remove any parent container margins/padding */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem !important;
    }
    
    /* Hide the default nav container completely */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"],
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] + div {
        display: none !important;
    }
    
    /* Make sidebar nav buttons look like plain text links */
    section[data-testid="stSidebar"] button[kind="secondary"],
    section[data-testid="stSidebar"] button[kind="tertiary"],
    section[data-testid="stSidebar"] button[kind="primary"] {
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0.25rem 0 !important;
        text-align: left !important;
        border-radius: 0 !important;
        font-weight: normal !important;
    }
    
    section[data-testid="stSidebar"] button[kind="primary"] p {
        color: #ff4b4b !important;
        font-weight: 600 !important;
    }
    
    section[data-testid="stSidebar"] button:hover {
        background: none !important;
    }
    
    section[data-testid="stSidebar"] button:hover p {
        color: #ff4b4b !important;
    }
    
    /* Job queue table styling */
    .job-table-header {
        background-color: #f0f0f0 !important;
        padding: 0.5rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
    }
    
    .job-table-header p {
        font-weight: bold !important;
        margin: 0 !important;
    }
    
    .job-row-even {
        background-color: #fafafa;
    }
    
    .job-row-odd {
        background-color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for settings persistence
def init_app_state():
    """Initialize application-wide session state."""
    if "app_initialized" not in st.session_state:
        st.session_state.app_initialized = True
        st.session_state.current_page = "Dashboard"
        
        # Load settings from file if exists
        settings_file = Path("app_settings.json")
        if settings_file.exists():
            try:
                with open(settings_file, "r") as f:
                    st.session_state.app_settings = json.load(f)
            except Exception:
                st.session_state.app_settings = get_default_settings()
        else:
            st.session_state.app_settings = get_default_settings()


def get_default_settings():
    """Get default application settings."""
    return {
        "comfyui_server_url": "http://3090.zero:8188",
        "default_width": 640,
        "default_height": 640,
        "default_fps": 16,
        "default_frames_per_segment": 81,
        "models": {
            "high_noise": "wan2.2_i2v_high_noise_14B_fp16.safetensors",
            "low_noise": "wan2.2_i2v_low_noise_14B_fp16.safetensors",
            "vae": "wan_2.1_vae.safetensors",
            "text_encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        },
        "generation_params": {
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
        },
        "default_negative_prompt": (
            "blurry, low quality, distorted, deformed, ugly, bad anatomy, watermark, text, logo, "
            "static, frozen, jerky motion, artifacts, noise, overexposed, underexposed"
        ),
        "segment_durations": {
            "3 seconds": 49,
            "4 seconds": 65,
            "5 seconds": 81,
        },
    }


def render_sidebar():
    """Render the sidebar navigation."""
    with st.sidebar:
        # App title with icon at top left
        st.markdown("## 🎬 Wan2.2 Video Generator")
        st.divider()
        
        # Navigation items with icons (link-style, left-justified)
        nav_items = [
            ("🏠", "Dashboard"),
            ("📋", "Job Queue"),
            ("🖼️", "Image Library"),
            ("⚙️", "Settings"),
        ]
        
        for icon, page_name in nav_items:
            is_active = st.session_state.current_page == page_name
            active_class = "active" if is_active else ""
            
            # Use columns to create left-justified clickable area
            col1, col2 = st.columns([0.15, 0.85])
            with col1:
                st.markdown(f"<span style='font-size: 1.1rem;'>{icon}</span>", unsafe_allow_html=True)
            with col2:
                if st.button(
                    page_name,
                    key=f"nav_{page_name}",
                    type="tertiary" if not is_active else "primary",
                ):
                    st.session_state.current_page = page_name
                    st.rerun()


def main():
    """Main application entry point."""
    init_app_state()
    render_sidebar()
    
    # Route to the appropriate page
    page = st.session_state.current_page
    
    if page == "Dashboard":
        dashboard.render()
    elif page == "Job Queue":
        job_queue.render()
    elif page == "Image Library":
        image_library.render()
    elif page == "Settings":
        settings.render()
    else:
        dashboard.render()


if __name__ == "__main__":
    main()
