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
from workflow_builder import build_workflow, calculate_stages, estimate_generation_time


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
                    
                    # Get start image path
                    start_image_path = state.get("start_image_path")
                    if not start_image_path:
                        # Try to find it in frames directory
                        start_img = frames_dir / "start_image.png" if frames_dir.exists() else None
                        if start_img and start_img.exists():
                            start_image_path = str(start_img)
                    
                    jobs.append({
                        "name": job_dir.name,
                        "path": str(job_dir),
                        "status": state.get("status", "unknown"),
                        "current_stage": state.get("current_stage", 0),
                        "total_stages": state.get("total_stages", 0),
                        "created_on": start_time_str,
                        "start_timestamp": start_time,
                        "thumbnail": thumbnail,
                        "start_image_path": start_image_path,
                        "num_segments": len(state.get("segment_paths", [])),
                        "prompts": state.get("prompts", []),
                        "segment_paths": state.get("segment_paths", []),
                        "frame_paths": state.get("frame_paths", []),
                        "config": state.get("config", {}),
                        "current_prompt_id": state.get("current_prompt_id"),
                    })
                except Exception:
                    continue
    
    return jobs


def render_job_table(jobs: list[dict]):
    """Render the job queue table with headers always visible."""
    # Table header with grey background
    st.markdown('<div class="job-table-header">', unsafe_allow_html=True)
    header_cols = st.columns([0.6, 2.5, 1.5, 1, 1, 0.8])
    with header_cols[0]:
        st.markdown("**Thumb**")
    with header_cols[1]:
        st.markdown("**Name**")
    with header_cols[2]:
        st.markdown("**Created On**")
    with header_cols[3]:
        st.markdown("**Status**")
    with header_cols[4]:
        st.markdown("**Progress**")
    with header_cols[5]:
        st.markdown("**Segs**")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Show message if no jobs
    if not jobs:
        st.info("No jobs in the queue. Click 'New Job' to start generating videos!")
        return
    
    # Table rows with alternating colors
    for i, job in enumerate(jobs):
        row_class = "job-row-even" if i % 2 == 0 else "job-row-odd"
        st.markdown(f'<div class="{row_class}">', unsafe_allow_html=True)
        cols = st.columns([0.6, 2.5, 1.5, 1, 1, 0.8])
        
        with cols[0]:
            # Thumbnail
            if job.get("thumbnail") and Path(job["thumbnail"]).exists():
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
            st.markdown(job.get("created_on", "Unknown"))
        
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
        st.markdown('</div>', unsafe_allow_html=True)


def cancel_job(job: dict):
    """Cancel a job - remove from ComfyUI queue and update local state."""
    client = get_comfyui_client()
    
    # Try to cancel in ComfyUI if there's an active prompt
    prompt_id = job.get("current_prompt_id")
    if prompt_id:
        # First try to interrupt if it's running
        client.interrupt_generation()
        # Then delete from queue
        success, msg = client.cancel_prompt(prompt_id)
        if not success:
            st.warning(f"Could not cancel in ComfyUI: {msg}")
    
    # Update local job state
    job_path = job.get("path")
    if job_path:
        state_file = Path(job_path) / "job_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
                
                state["status"] = "cancelled"
                state["current_prompt_id"] = None
                
                with open(state_file, "w") as f:
                    json.dump(state, f, indent=2)
                
                st.success("Job cancelled successfully")
            except Exception as e:
                st.error(f"Error updating job state: {e}")
    
    # Reset view state
    st.session_state.show_job_detail = False
    st.session_state.selected_job = None


def render_job_detail(job: dict):
    """Render the job detail view with ComfyUI status."""
    st.subheader(f"Job: {job['name']}")
    
    # Action buttons row
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])
    
    with btn_col1:
        if st.button("< Back to Job Queue"):
            st.session_state.show_job_detail = False
            st.session_state.selected_job = None
            st.rerun()
    
    with btn_col2:
        # Show cancel button for active jobs
        job_status = job.get("status", "")
        if job_status in ["generating", "idle", "pending", "review"]:
            if st.button("Cancel Job", type="secondary"):
                cancel_job(job)
                st.rerun()
    
    st.divider()
    
    # Job status overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status = job["status"]
        st.metric("Status", status)
    
    with col2:
        st.metric("Current Stage", f"{job['current_stage']} / {job['total_stages']}")
    
    with col3:
        st.metric("Segments", job['num_segments'])
    
    with col4:
        st.metric("Created On", job.get('created_on', 'Unknown'))
    
    # Show ComfyUI status if job has an active prompt
    prompt_id = job.get("current_prompt_id")
    if prompt_id and job["status"] in ["generating", "idle"]:
        st.divider()
        st.markdown("**ComfyUI Status**")
        client = get_comfyui_client()
        poll_status, progress, outputs, progress_info = client.poll_once(prompt_id)
        
        if poll_status == "pending":
            st.info("Queued - waiting for ComfyUI server...")
        elif poll_status == "running":
            percent = progress_info.get("percent", progress * 100)
            node_info = progress_info.get("node", "")
            progress_text = f"{percent:.1f}% complete"
            if node_info:
                progress_text += f" - {node_info}"
            st.progress(min(progress, 0.99), text=progress_text)
        elif poll_status == "complete":
            st.success("Generation complete!")
        elif poll_status == "error":
            st.error(f"Generation failed: {outputs.get('error', 'Unknown error')}")
    
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
    start_image_path = job.get("start_image_path")
    
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
            
            # Determine start thumbnail for this stage
            if stage_num == 1:
                # First stage uses the original start image
                start_thumb = start_image_path
            else:
                # Subsequent stages use the final frame from previous stage
                prev_index = i - 1
                start_thumb = frame_paths[prev_index] if prev_index < len(frame_paths) else None
            
            # Determine final frame thumbnail for this stage
            final_thumb = frame_paths[i] if i < len(frame_paths) else None
            
            with st.container(border=True):
                # Layout: Start Image | Stage Info + Prompt | Status | Final Frame
                cols = st.columns([1, 3, 1, 1])
                
                with cols[0]:
                    st.caption("Start")
                    if start_thumb and Path(start_thumb).exists():
                        st.image(start_thumb, width=70)
                    else:
                        st.markdown("—")
                
                with cols[1]:
                    st.markdown(f"**Stage {stage_num}**")
                    # Show prompt if available
                    if i < len(prompts):
                        st.markdown(f"*{prompts[i][:80]}{'...' if len(prompts[i]) > 80 else ''}*")
                    else:
                        st.markdown("*Prompt pending...*")
                
                with cols[2]:
                    st.caption("Status")
                    st.markdown(f":{status_color}[{status_icon}]")
                
                with cols[3]:
                    st.caption("Final")
                    if final_thumb and Path(final_thumb).exists():
                        st.image(final_thumb, width=70)
                    else:
                        st.markdown("—")
        
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
        
        # Calculate stage info (no timeline preview per user request)
        num_frames = SEGMENT_DURATIONS[segment_duration]
        stages = calculate_stages(total_duration, fps)
        num_stages = len(stages)
        
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
                
                # Save the uploaded image locally
                start_image_path = output_dir / FRAMES_DIR / "start_image.png"
                with open(start_image_path, "wb") as f:
                    f.write(uploaded_image.getvalue())
                
                # Upload image to ComfyUI server
                client = get_comfyui_client()
                upload_success, upload_msg, uploaded_filename = client.upload_image(
                    str(start_image_path),
                    subfolder="input",
                    overwrite=True
                )
                
                if not upload_success:
                    st.error(f"Failed to upload image to ComfyUI: {upload_msg}")
                else:
                    # Build workflow and submit to ComfyUI
                    workflow = build_workflow(
                        positive_prompt=initial_prompt,
                        image_filename=uploaded_filename,
                        width=width,
                        height=height,
                        num_frames=num_frames,
                        fps=fps,
                        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                        output_prefix=output_filename,
                        seed=None,  # Random seed
                        high_noise_lora=config.get("high_noise_lora"),
                        low_noise_lora=config.get("low_noise_lora"),
                    )
                    
                    # Queue the prompt
                    queue_success, queue_msg, prompt_id = client.queue_prompt(workflow)
                    
                    if not queue_success:
                        st.error(f"Failed to queue job: {queue_msg}")
                        # Still save job state but with error status
                        job_state = {
                            "status": "error",
                            "error_message": queue_msg,
                            "current_stage": 1,
                            "total_stages": num_stages,
                            "stages": stages,
                            "prompts": [initial_prompt],
                            "segment_paths": [],
                            "frame_paths": [],
                            "config": config,
                            "generation_start_time": time.time(),
                            "output_dir": str(output_dir),
                            "start_image_path": str(start_image_path),
                        }
                    else:
                        # Create job state with generating status and prompt_id
                        job_state = {
                            "status": "generating",
                            "current_stage": 1,
                            "total_stages": num_stages,
                            "stages": stages,
                            "prompts": [initial_prompt],
                            "segment_paths": [],
                            "frame_paths": [],
                            "config": config,
                            "generation_start_time": time.time(),
                            "output_dir": str(output_dir),
                            "start_image_path": str(start_image_path),
                            "current_prompt_id": prompt_id,
                            "uploaded_image_filename": uploaded_filename,
                        }
                        st.success(f"Job '{job_name}' submitted to ComfyUI queue!")
                    
                    # Save job state
                    state_file = output_dir / "job_state.json"
                    with open(state_file, "w") as f:
                        json.dump(job_state, f, indent=2)
                    
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
