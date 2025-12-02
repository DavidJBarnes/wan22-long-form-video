"""Job Queue page for the Wan2.2 Video Generator app."""

import streamlit as st
from pathlib import Path
import json
import time
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    COMFYUI_SERVER_URL,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
    DEFAULT_FPS,
    DEFAULT_FRAMES_PER_SEGMENT,
    DEFAULT_NEGATIVE_PROMPT,
    SEGMENT_DURATIONS,
    OUTPUT_DIR,
    SEGMENTS_DIR,
    FRAMES_DIR,
)
from comfyui_api import ComfyUIClient
from workflow_builder import calculate_stages, estimate_generation_time


def get_all_jobs() -> list[dict]:
    """Get all jobs from the output directory.
    
    Returns:
        List of job info dicts sorted by modification time (newest first)
    """
    jobs = []
    output_dir = Path("output")
    
    if not output_dir.exists():
        return jobs
    
    for job_dir in sorted(output_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if job_dir.is_dir():
            state_file = job_dir / "job_state.json"
            if state_file.exists():
                try:
                    with open(state_file, "r") as f:
                        state = json.load(f)
                    
                    # Get thumbnail if available
                    thumbnail = None
                    frames_dir = job_dir / "frames"
                    if frames_dir.exists():
                        frame_files = list(frames_dir.glob("*.png"))
                        if frame_files:
                            thumbnail = str(frame_files[0])
                    
                    # Format start time
                    start_time = state.get("generation_start_time")
                    if start_time:
                        try:
                            start_dt = datetime.fromtimestamp(start_time)
                            start_time_str = start_dt.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            start_time_str = "Unknown"
                    else:
                        start_time_str = "Unknown"
                    
                    jobs.append({
                        "name": job_dir.name,
                        "path": str(job_dir),
                        "status": state.get("status", "unknown"),
                        "current_stage": state.get("current_stage", 0),
                        "total_stages": state.get("total_stages", 0),
                        "start_time": start_time_str,
                        "start_timestamp": start_time,
                        "thumbnail": thumbnail,
                        "num_segments": len(state.get("segment_paths", [])),
                        "prompts": state.get("prompts", []),
                        "segment_paths": state.get("segment_paths", []),
                        "frame_paths": state.get("frame_paths", []),
                        "config": state.get("config", {}),
                    })
                except Exception:
                    continue
    
    return jobs


def render_job_table(jobs: list[dict]):
    """Render the job queue table with headers always visible."""
    # Table header - always show
    header_cols = st.columns([0.6, 2.5, 1.5, 1, 1, 0.8])
    with header_cols[0]:
        st.markdown("**Thumb**")
    with header_cols[1]:
        st.markdown("**Name**")
    with header_cols[2]:
        st.markdown("**Start Time**")
    with header_cols[3]:
        st.markdown("**Status**")
    with header_cols[4]:
        st.markdown("**Progress**")
    with header_cols[5]:
        st.markdown("**Segs**")
    
    st.divider()
    
    # Show message if no jobs
    if not jobs:
        st.info("No jobs in the queue. Click 'New Job' to start generating videos!")
        return
    
    # Table rows
    for i, job in enumerate(jobs):
        cols = st.columns([0.6, 2.5, 1.5, 1, 1, 0.8])
        
        with cols[0]:
            # Thumbnail
            if job["thumbnail"] and Path(job["thumbnail"]).exists():
                st.image(job["thumbnail"], width=50)
            else:
                st.markdown("🎬")
        
        with cols[1]:
            # Clickable name
            if st.button(job["name"][:30], key=f"job_btn_{job['name']}"):
                st.session_state.selected_job = job
                st.session_state.show_job_detail = True
                st.rerun()
        
        with cols[2]:
            st.markdown(job["start_time"])
        
        with cols[3]:
            status = job["status"]
            status_colors = {
                "complete": "green",
                "generating": "orange",
                "review": "blue",
                "error": "red",
                "idle": "gray",
                "finalizing": "orange",
            }
            color = status_colors.get(status, "gray")
            st.markdown(f":{color}[{status}]")
        
        with cols[4]:
            st.markdown(f"{job['current_stage']}/{job['total_stages']}")
        
        with cols[5]:
            st.markdown(f"{job['num_segments']}")


def render_job_detail(job: dict):
    """Render the job detail view."""
    st.subheader(f"Job: {job['name']}")
    
    # Back button
    if st.button("< Back to Job Queue"):
        st.session_state.show_job_detail = False
        st.session_state.selected_job = None
        st.rerun()
    
    st.divider()
    
    # Job status overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status = job["status"]
        status_colors = {
            "complete": "green",
            "generating": "orange",
            "review": "blue",
            "error": "red",
            "idle": "gray",
            "finalizing": "orange",
        }
        color = status_colors.get(status, "gray")
        st.metric("Status", status)
    
    with col2:
        st.metric("Current Stage", f"{job['current_stage']} / {job['total_stages']}")
    
    with col3:
        st.metric("Segments", job['num_segments'])
    
    with col4:
        st.metric("Started", job['start_time'])
    
    st.divider()
    
    # Configuration info
    config = job.get("config", {})
    if config:
        with st.expander("Configuration", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Resolution:** {config.get('width', 'N/A')}x{config.get('height', 'N/A')}")
                st.markdown(f"**FPS:** {config.get('fps', 'N/A')}")
            with col2:
                st.markdown(f"**Segment Duration:** {config.get('segment_duration', 'N/A')}")
                st.markdown(f"**Output Filename:** {config.get('output_filename', 'N/A')}")
    
    st.divider()
    
    # Sequence timeline
    st.subheader("Sequence Timeline")
    
    prompts = job.get("prompts", [])
    segment_paths = job.get("segment_paths", [])
    frame_paths = job.get("frame_paths", [])
    total_stages = job.get("total_stages", 0)
    current_stage = job.get("current_stage", 0)
    
    if prompts or total_stages > 0:
        for i in range(max(len(prompts), total_stages)):
            stage_num = i + 1
            
            # Determine stage status
            if stage_num < current_stage:
                stage_status = "complete"
                status_icon = "[done]"
                status_color = "green"
            elif stage_num == current_stage:
                if job["status"] == "complete":
                    stage_status = "complete"
                    status_icon = "[done]"
                    status_color = "green"
                else:
                    stage_status = "in_progress"
                    status_icon = "[current]"
                    status_color = "orange"
            else:
                stage_status = "pending"
                status_icon = "[pending]"
                status_color = "gray"
            
            with st.container(border=True):
                cols = st.columns([1, 4, 1])
                
                with cols[0]:
                    st.markdown(f"**Stage {stage_num}**")
                    st.markdown(f":{status_color}[{status_icon}]")
                
                with cols[1]:
                    # Show prompt if available
                    if i < len(prompts):
                        st.markdown(f"*{prompts[i][:100]}{'...' if len(prompts[i]) > 100 else ''}*")
                    else:
                        st.markdown("*Prompt pending...*")
                
                with cols[2]:
                    # Show thumbnail if segment is complete
                    if i < len(frame_paths):
                        frame_path = Path(frame_paths[i])
                        if frame_path.exists():
                            st.image(str(frame_path), width=80)
        
        # Future stages indicator
        if total_stages > len(prompts):
            remaining = total_stages - len(prompts)
            st.info(f"{remaining} more stage(s) to be generated")
    else:
        st.info("No sequence data available yet.")
    
    # Video segments
    if segment_paths:
        st.divider()
        st.subheader("Generated Segments")
        
        for i, seg_path in enumerate(segment_paths):
            seg_path = Path(seg_path)
            if seg_path.exists():
                with st.expander(f"Segment {i + 1}: {seg_path.name}", expanded=False):
                    try:
                        with open(seg_path, "rb") as f:
                            video_bytes = f.read()
                        st.video(video_bytes)
                    except Exception as e:
                        st.error(f"Error loading video: {e}")


def get_comfyui_client() -> ComfyUIClient:
    """Get or create the ComfyUI client."""
    if "comfyui_client" not in st.session_state or st.session_state.comfyui_client is None:
        st.session_state.comfyui_client = ComfyUIClient(COMFYUI_SERVER_URL)
    return st.session_state.comfyui_client


def setup_output_directories(base_name: str) -> Path:
    """Set up output directories for the generation session."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(OUTPUT_DIR) / f"{base_name}_{timestamp}"
    
    (output_dir / SEGMENTS_DIR).mkdir(parents=True, exist_ok=True)
    (output_dir / FRAMES_DIR).mkdir(parents=True, exist_ok=True)
    
    return output_dir


def render_new_job_form():
    """Render the new job creation form with all configuration options."""
    st.subheader("Create New Job")
    
    # Back button
    if st.button("< Back to Job Queue"):
        st.session_state.show_new_job_form = False
        st.rerun()
    
    st.divider()
    
    with st.form("new_job_form"):
        # Job name (new field)
        job_name = st.text_input(
            "Job Name",
            value="",
            placeholder="Enter a name for this job",
            help="A descriptive name to identify this video generation job"
        )
        
        st.divider()
        
        # Two-column layout for configuration
        col1, col2 = st.columns(2)
        
        with col1:
            total_duration = st.number_input(
                "Total Duration (seconds)",
                min_value=3,
                max_value=300,
                value=30,
                step=1,
                help="Target total video length"
            )
            
            width = st.number_input(
                "Width",
                min_value=256,
                max_value=1280,
                value=DEFAULT_WIDTH,
                step=64,
                help="Video width in pixels"
            )
            
            height = st.number_input(
                "Height",
                min_value=256,
                max_value=1280,
                value=DEFAULT_HEIGHT,
                step=64,
                help="Video height in pixels"
            )
        
        with col2:
            fps = st.number_input(
                "FPS",
                min_value=8,
                max_value=30,
                value=DEFAULT_FPS,
                step=1,
                help="Frames per second"
            )
            
            segment_duration = st.selectbox(
                "Segment Duration",
                options=list(SEGMENT_DURATIONS.keys()),
                index=2,  # Default to 5 seconds
                help="Duration of each video segment"
            )
            
            output_filename = st.text_input(
                "Output Filename",
                value="my_video",
                help="Base name for the final video file"
            )
        
        st.divider()
        
        # LoRA selection (optional)
        st.markdown("**LoRA Models (Optional)**")
        st.caption("Select LoRA models to apply during generation. Both are optional.")
        
        # Get available LoRAs from ComfyUI
        client = get_comfyui_client()
        available_loras = client.get_loras()
        lora_options = ["None"] + available_loras
        
        lora_col1, lora_col2 = st.columns(2)
        with lora_col1:
            high_noise_lora = st.selectbox(
                "High Noise LoRA",
                options=lora_options,
                index=0,
                help="LoRA to apply to the high noise model (first pass)"
            )
        
        with lora_col2:
            low_noise_lora = st.selectbox(
                "Low Noise LoRA",
                options=lora_options,
                index=0,
                help="LoRA to apply to the low noise model (second pass)"
            )
        
        st.divider()
        
        # Start image upload
        st.markdown("**Start Image**")
        uploaded_image = st.file_uploader(
            "Upload the initial frame",
            type=["png", "jpg", "jpeg", "webp"],
            help="This image will be the first frame of your video"
        )
        
        if uploaded_image:
            st.image(uploaded_image, caption="Start Image Preview", width=300)
        
        st.divider()
        
        # Initial prompt
        st.markdown("**Initial Prompt**")
        initial_prompt = st.text_area(
            "Describe what should happen in the first segment",
            height=100,
            placeholder="Example: A person walks through a beautiful forest, sunlight filtering through the trees...",
            help="Be descriptive about the motion and scene"
        )
        
        # Calculate and display stage info
        num_frames = SEGMENT_DURATIONS[segment_duration]
        stages = calculate_stages(total_duration, fps)
        num_stages = len(stages)
        time_estimate = estimate_generation_time(num_frames, num_stages)
        
        st.divider()
        
        # Timeline preview
        st.markdown("**Timeline Preview**")
        st.info(
            f"This will generate **{num_stages} segments** of ~{segment_duration.split()[0]} seconds each. "
            f"Estimated generation time: **{time_estimate}**"
        )
        
        # Visual timeline representation
        timeline_cols = st.columns(min(num_stages, 10))
        for i, col in enumerate(timeline_cols):
            if i < num_stages:
                with col:
                    st.markdown(f"**{i+1}**")
                    if i == 0:
                        st.markdown(":blue[Start]")
                    elif i == num_stages - 1:
                        st.markdown(":green[End]")
                    else:
                        st.markdown(":gray[...]")
        
        if num_stages > 10:
            st.caption(f"... and {num_stages - 10} more segments")
        
        st.divider()
        
        # Submit button
        submitted = st.form_submit_button("Start Generation", use_container_width=True, type="primary")
        
        if submitted:
            # Validation
            errors = []
            if not job_name.strip():
                errors.append("Please enter a job name")
            if not uploaded_image:
                errors.append("Please upload a start image")
            if not initial_prompt.strip():
                errors.append("Please enter an initial prompt")
            if not output_filename.strip():
                errors.append("Please enter an output filename")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Save configuration
                config = {
                    "job_name": job_name,
                    "total_duration": total_duration,
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "segment_duration": segment_duration,
                    "num_frames": num_frames,
                    "output_filename": output_filename,
                    "high_noise_lora": high_noise_lora if high_noise_lora != "None" else None,
                    "low_noise_lora": low_noise_lora if low_noise_lora != "None" else None,
                }
                
                # Set up output directories using job name
                output_dir = setup_output_directories(job_name.replace(" ", "_"))
                
                # Save the uploaded image
                start_image_path = output_dir / FRAMES_DIR / "start_image.png"
                with open(start_image_path, "wb") as f:
                    f.write(uploaded_image.getvalue())
                
                # Create initial job state
                job_state = {
                    "status": "idle",
                    "current_stage": 1,
                    "total_stages": num_stages,
                    "stages": stages,
                    "prompts": [initial_prompt],
                    "segment_paths": [],
                    "frame_paths": [],
                    "config": config,
                    "generation_start_time": time.time(),
                    "output_dir": str(output_dir),
                }
                
                # Save job state
                state_file = output_dir / "job_state.json"
                with open(state_file, "w") as f:
                    json.dump(job_state, f, indent=2)
                
                st.success(f"Job '{job_name}' created successfully!")
                st.info(f"Output directory: {output_dir}")
                st.info("To start generation, use the legacy generator (`streamlit run wan_video_generator.py`) and load this job from the sidebar.")
                
                # Reset form state
                st.session_state.show_new_job_form = False
                st.rerun()


def render():
    """Render the job queue page."""
    st.title("Job Queue")
    st.caption("Manage your video generation jobs")
    
    # Initialize state
    if "show_job_detail" not in st.session_state:
        st.session_state.show_job_detail = False
    if "selected_job" not in st.session_state:
        st.session_state.selected_job = None
    if "show_new_job_form" not in st.session_state:
        st.session_state.show_new_job_form = False
    
    # Route to appropriate view
    if st.session_state.show_new_job_form:
        render_new_job_form()
    elif st.session_state.show_job_detail and st.session_state.selected_job:
        render_job_detail(st.session_state.selected_job)
    else:
        # New Job button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("+ New Job", type="primary", use_container_width=True):
                st.session_state.show_new_job_form = True
                st.rerun()
        
        st.divider()
        
        # Get and display jobs
        jobs = get_all_jobs()
        render_job_table(jobs)
