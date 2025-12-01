"""
Wan2.2 Long Video Generator - Streamlit Application

A web application for generating long-form videos using the Wan2.2 14B I2V model
by chaining multiple short video segments together.
"""

import streamlit as st
import time
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

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
from video_utils import (
    extract_last_frame,
    concatenate_videos,
    concatenate_videos_reencode,
    check_ffmpeg_available,
    get_video_info,
)


# Page configuration
st.set_page_config(
    page_title="Wan2.2 Long Video Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "status": "idle",  # idle, configuring, generating, review, complete, error
        "current_stage": 0,
        "total_stages": 0,
        "stages": [],
        "prompts": [],
        "segment_paths": [],
        "frame_paths": [],
        "current_prompt_id": None,
        "last_frame_path": None,
        "start_image_path": None,
        "config": {},
        "generation_start_time": None,
        "stage_start_time": None,
        "error_message": None,
        "comfyui_client": None,
        "output_dir": None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session():
    """Reset session state for a new generation."""
    st.session_state.status = "idle"
    st.session_state.current_stage = 0
    st.session_state.total_stages = 0
    st.session_state.stages = []
    st.session_state.prompts = []
    st.session_state.segment_paths = []
    st.session_state.frame_paths = []
    st.session_state.current_prompt_id = None
    st.session_state.last_frame_path = None
    st.session_state.start_image_path = None
    st.session_state.config = {}
    st.session_state.generation_start_time = None
    st.session_state.stage_start_time = None
    st.session_state.error_message = None


def get_client() -> ComfyUIClient:
    """Get or create the ComfyUI client."""
    if st.session_state.comfyui_client is None:
        st.session_state.comfyui_client = ComfyUIClient(COMFYUI_SERVER_URL)
    return st.session_state.comfyui_client


def setup_output_directories(base_name: str) -> Path:
    """Set up output directories for the generation session."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(OUTPUT_DIR) / f"{base_name}_{timestamp}"
    
    (output_dir / SEGMENTS_DIR).mkdir(parents=True, exist_ok=True)
    (output_dir / FRAMES_DIR).mkdir(parents=True, exist_ok=True)
    
    st.session_state.output_dir = output_dir
    return output_dir


def render_header():
    """Render the application header."""
    st.title("🎬 Wan2.2 Long Video Generator")
    st.markdown(
        "Generate long-form videos by chaining multiple segments with seamless transitions."
    )


def render_server_status():
    """Render the ComfyUI server connection status."""
    client = get_client()
    connected, message = client.check_connection()
    
    if connected:
        queue_pending, queue_running = client.get_queue_status()
        st.sidebar.success(f"✓ {message}")
        if queue_running > 0 or queue_pending > 0:
            st.sidebar.info(f"Queue: {queue_running} running, {queue_pending} pending")
    else:
        st.sidebar.error(f"✗ {message}")
        st.sidebar.warning("Please ensure ComfyUI is running and accessible.")
    
    return connected


def render_configuration_form():
    """Render the initial configuration form."""
    st.header("Configuration")
    
    with st.form("config_form"):
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
        
        st.subheader("Start Image")
        uploaded_image = st.file_uploader(
            "Upload the initial frame",
            type=["png", "jpg", "jpeg", "webp"],
            help="This image will be the first frame of your video"
        )
        
        if uploaded_image:
            st.image(uploaded_image, caption="Start Image Preview", width=300)
        
        st.subheader("Initial Prompt")
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
        
        st.info(
            f"This will generate **{num_stages} stages** of ~{segment_duration.split()[0]} seconds each. "
            f"Estimated generation time: **{time_estimate}**"
        )
        
        submitted = st.form_submit_button("🚀 Start Generation", use_container_width=True)
        
        if submitted:
            # Validation
            errors = []
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
                st.session_state.config = {
                    "total_duration": total_duration,
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "segment_duration": segment_duration,
                    "num_frames": num_frames,
                    "output_filename": output_filename,
                }
                
                # Set up output directories
                output_dir = setup_output_directories(output_filename)
                
                # Save the uploaded image
                start_image_path = output_dir / FRAMES_DIR / "start_image.png"
                with open(start_image_path, "wb") as f:
                    f.write(uploaded_image.getvalue())
                st.session_state.start_image_path = start_image_path
                st.session_state.last_frame_path = start_image_path
                
                # Set up stages
                st.session_state.stages = stages
                st.session_state.total_stages = num_stages
                st.session_state.current_stage = 1
                st.session_state.prompts = [initial_prompt]
                
                # Start generation
                st.session_state.status = "generating"
                st.session_state.generation_start_time = time.time()
                
                st.rerun()


def render_generation_progress():
    """Render the generation progress view."""
    st.header(f"Generating Stage {st.session_state.current_stage} of {st.session_state.total_stages}")
    
    # Overall stage progress bar
    stage_progress = (st.session_state.current_stage - 1) / st.session_state.total_stages
    st.progress(stage_progress, text=f"Overall: Stage {st.session_state.current_stage}/{st.session_state.total_stages}")
    
    # Show current starting frame
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Starting Frame")
        if st.session_state.last_frame_path and Path(st.session_state.last_frame_path).exists():
            st.image(str(st.session_state.last_frame_path), caption="Input for this stage")
    
    with col2:
        st.subheader("Current Prompt")
        current_prompt = st.session_state.prompts[-1] if st.session_state.prompts else ""
        st.text_area("Prompt", value=current_prompt, disabled=True, height=100)
    
    # Generation progress section
    st.subheader("Generation Progress")
    progress_bar = st.progress(0.0, text="Initializing...")
    status_text = st.empty()
    
    # Start generation if not already running
    if st.session_state.current_prompt_id is None:
        status_text.info("Uploading image and starting generation...")
        success = start_stage_generation()
        if not success:
            st.session_state.status = "error"
            st.rerun()
    
    # Poll for completion with progress updates
    if st.session_state.current_prompt_id:
        status_text.info("Generating video segment... This may take several minutes.")
        
        # Create a progress callback that updates the UI
        def update_progress(percent: float, status: str):
            progress_bar.progress(min(percent, 1.0), text=status)
            status_text.info(status)
        
        success, message, outputs = poll_generation_with_progress(update_progress)
        
        if success:
            progress_bar.progress(1.0, text="Generation complete!")
            # Process the output
            process_success = process_stage_output(outputs)
            if process_success:
                st.session_state.status = "review"
                st.session_state.current_prompt_id = None
            else:
                st.session_state.status = "error"
            st.rerun()
        elif "timed out" in message.lower() or "failed" in message.lower():
            st.session_state.error_message = message
            st.session_state.status = "error"
            st.rerun()


def start_stage_generation() -> bool:
    """Start generation for the current stage."""
    client = get_client()
    config = st.session_state.config
    
    # Upload the current frame to ComfyUI
    frame_path = Path(st.session_state.last_frame_path)
    success, message, uploaded_filename = client.upload_image(frame_path)
    
    if not success:
        st.session_state.error_message = f"Failed to upload image: {message}"
        return False
    
    # Build the workflow
    current_prompt = st.session_state.prompts[-1]
    stage_num = st.session_state.current_stage
    
    output_prefix = f"wan_segment_{stage_num:03d}"
    
    workflow = build_workflow(
        positive_prompt=current_prompt,
        image_filename=uploaded_filename,
        width=config["width"],
        height=config["height"],
        num_frames=config["num_frames"],
        fps=config["fps"],
        output_prefix=output_prefix
    )
    
    # Queue the prompt
    success, message, prompt_id = client.queue_prompt(workflow)
    
    if not success:
        st.session_state.error_message = f"Failed to queue prompt: {message}"
        return False
    
    st.session_state.current_prompt_id = prompt_id
    st.session_state.stage_start_time = time.time()
    
    return True


def poll_generation() -> tuple[bool, str, dict]:
    """Poll for generation completion (without progress callback)."""
    client = get_client()
    prompt_id = st.session_state.current_prompt_id
    
    return client.wait_for_completion(prompt_id)


def poll_generation_with_progress(progress_callback) -> tuple[bool, str, dict]:
    """Poll for generation completion with progress updates.
    
    Args:
        progress_callback: Function to call with (percent, status_text) updates
    """
    client = get_client()
    prompt_id = st.session_state.current_prompt_id
    
    # Our workflow has 15 nodes
    return client.wait_for_completion(prompt_id, progress_callback=progress_callback, total_nodes=15)


def process_stage_output(outputs: dict) -> bool:
    """Process the output from a completed stage."""
    import json
    
    client = get_client()
    config = st.session_state.config
    stage_num = st.session_state.current_stage
    output_dir = st.session_state.output_dir
    
    # Debug: Log the outputs structure to help diagnose issues
    debug_log_path = output_dir / "debug_outputs.json"
    try:
        with open(debug_log_path, "w") as f:
            json.dump(outputs, f, indent=2, default=str)
    except Exception:
        pass  # Ignore debug logging errors
    
    # Find the video output in the outputs
    # ComfyUI may use different keys: "videos", "images", or "gifs"
    video_filename = None
    video_subfolder = ""
    video_type = "output"
    
    # Video file extensions to look for
    video_extensions = (".mp4", ".webm", ".gif", ".avi", ".mov")
    
    for node_id, node_output in outputs.items():
        # Try common keys that ComfyUI uses for outputs
        for key in ("videos", "images", "gifs"):
            if key in node_output:
                for item in node_output[key]:
                    fname = item.get("filename", "")
                    # Check if this is a video file by extension
                    if fname.lower().endswith(video_extensions):
                        video_filename = fname
                        video_subfolder = item.get("subfolder", "")
                        video_type = item.get("type", "output")
                        break
                if video_filename:
                    break
        if video_filename:
            break
    
    if not video_filename:
        # Provide more helpful error message with debug info
        available_keys = []
        for node_id, node_output in outputs.items():
            if isinstance(node_output, dict):
                available_keys.append(f"Node {node_id}: {list(node_output.keys())}")
        debug_info = "; ".join(available_keys) if available_keys else "No output nodes found"
        st.session_state.error_message = f"No video output found in generation results. Debug: {debug_info}. Check {debug_log_path} for full output."
        return False
    
    # Download the video
    success, video_data = client.download_output(
        video_filename,
        subfolder=video_subfolder,
        output_type=video_type
    )
    
    if not success:
        st.session_state.error_message = "Failed to download generated video"
        return False
    
    # Save the video segment
    segment_path = output_dir / SEGMENTS_DIR / f"segment_{stage_num:03d}.mp4"
    with open(segment_path, "wb") as f:
        f.write(video_data)
    
    st.session_state.segment_paths.append(segment_path)
    
    # Extract the last frame
    frame_path = output_dir / FRAMES_DIR / f"frame_{stage_num:03d}.png"
    success, message = extract_last_frame(segment_path, frame_path)
    
    if not success:
        st.session_state.error_message = f"Failed to extract last frame: {message}"
        return False
    
    st.session_state.frame_paths.append(frame_path)
    st.session_state.last_frame_path = frame_path
    
    return True


def render_review_screen():
    """Render the review screen after a stage completes."""
    stage_num = st.session_state.current_stage
    total_stages = st.session_state.total_stages
    
    st.header(f"Stage {stage_num} of {total_stages} Complete")
    
    # Progress bar
    progress = stage_num / total_stages
    st.progress(progress, text=f"Progress: {stage_num}/{total_stages} stages")
    
    # Show the last frame
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Last Frame (Next Stage Start)")
        if st.session_state.last_frame_path:
            st.image(str(st.session_state.last_frame_path), caption="This will be the starting frame for the next stage")
    
    with col2:
        st.subheader("Stage Statistics")
        if st.session_state.stage_start_time:
            elapsed = time.time() - st.session_state.stage_start_time
            st.metric("Generation Time", f"{elapsed:.1f}s")
        
        config = st.session_state.config
        st.metric("Frames Generated", config["num_frames"])
        st.metric("Segment Duration", f"{config['num_frames'] / config['fps']:.1f}s")
    
    # Check if this was the last stage
    if stage_num >= total_stages:
        st.success("🎉 All stages complete! Ready to finalize video.")
        
        if st.button("🎬 Finalize Video", use_container_width=True, type="primary"):
            st.session_state.status = "finalizing"
            st.rerun()
        
        if st.button("➕ Add More Stages", use_container_width=True):
            st.session_state.total_stages += 1
            st.session_state.stages.append({
                "stage_number": st.session_state.total_stages,
                "duration_seconds": int(st.session_state.config["segment_duration"].split()[0]),
                "num_frames": st.session_state.config["num_frames"]
            })
            # Show prompt input for new stage
            render_next_prompt_input()
    else:
        render_next_prompt_input()


def render_next_prompt_input():
    """Render the prompt input for the next stage."""
    st.subheader("Next Stage Prompt")
    
    # Show previous prompts for context
    with st.expander("Previous Prompts", expanded=False):
        for i, prompt in enumerate(st.session_state.prompts, 1):
            st.text(f"Stage {i}: {prompt[:100]}...")
    
    next_prompt = st.text_area(
        "Describe what should happen next",
        height=150,
        placeholder="Based on the frame above, describe the next action or scene...",
        key="next_prompt_input"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ Continue", use_container_width=True, type="primary"):
            if next_prompt.strip():
                st.session_state.prompts.append(next_prompt)
                st.session_state.current_stage += 1
                st.session_state.status = "generating"
                st.rerun()
            else:
                st.error("Please enter a prompt for the next stage")
    
    with col2:
        if st.button("🔄 Regenerate", use_container_width=True):
            # Keep the same starting frame but allow prompt modification
            regenerate_prompt = st.session_state.prompts[-1]
            new_prompt = st.text_input("Modify prompt for regeneration", value=regenerate_prompt)
            if st.button("Confirm Regenerate"):
                st.session_state.prompts[-1] = new_prompt
                # Remove the last segment and frame
                if st.session_state.segment_paths:
                    last_segment = st.session_state.segment_paths.pop()
                    if last_segment.exists():
                        last_segment.unlink()
                if st.session_state.frame_paths:
                    last_frame = st.session_state.frame_paths.pop()
                    # Restore previous frame as last frame
                    if st.session_state.frame_paths:
                        st.session_state.last_frame_path = st.session_state.frame_paths[-1]
                    else:
                        st.session_state.last_frame_path = st.session_state.start_image_path
                
                st.session_state.status = "generating"
                st.rerun()
    
    with col3:
        if st.button("❌ Cancel", use_container_width=True):
            if st.session_state.segment_paths:
                st.warning(f"You have {len(st.session_state.segment_paths)} completed segments. Cancel will save progress.")
            if st.button("Confirm Cancel"):
                st.session_state.status = "complete"
                st.rerun()


def render_finalizing():
    """Render the finalizing screen."""
    st.header("Finalizing Video")
    
    with st.spinner("Concatenating video segments..."):
        output_dir = st.session_state.output_dir
        config = st.session_state.config
        
        final_path = output_dir / f"{config['output_filename']}_final.mp4"
        
        # Try copy mode first (faster)
        success, message = concatenate_videos(
            st.session_state.segment_paths,
            final_path,
            config["fps"]
        )
        
        # If copy mode fails, try re-encoding
        if not success:
            st.warning("Copy mode failed, trying re-encoding...")
            success, message = concatenate_videos_reencode(
                st.session_state.segment_paths,
                final_path,
                config["fps"]
            )
        
        if success:
            st.session_state.final_video_path = final_path
            st.session_state.status = "complete"
        else:
            st.session_state.error_message = message
            st.session_state.status = "error"
        
        st.rerun()


def render_complete():
    """Render the completion screen."""
    st.header("🎉 Video Generation Complete!")
    
    output_dir = st.session_state.output_dir
    config = st.session_state.config
    
    # Show final video if available
    final_path = output_dir / f"{config['output_filename']}_final.mp4"
    
    if final_path.exists():
        st.subheader("Final Video")
        st.video(str(final_path))
        
        # Download button
        with open(final_path, "rb") as f:
            st.download_button(
                "📥 Download Final Video",
                f,
                file_name=final_path.name,
                mime="video/mp4",
                use_container_width=True
            )
        
        # Video info
        video_info = get_video_info(final_path)
        if video_info:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Duration", f"{video_info['duration']:.1f}s")
            with col2:
                st.metric("Frames", video_info['frame_count'])
            with col3:
                st.metric("Resolution", f"{video_info['width']}x{video_info['height']}")
            with col4:
                st.metric("FPS", f"{video_info['fps']:.1f}")
    
    # Generation summary
    st.subheader("Generation Summary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Stages", len(st.session_state.segment_paths))
        if st.session_state.generation_start_time:
            total_time = time.time() - st.session_state.generation_start_time
            minutes = int(total_time // 60)
            seconds = int(total_time % 60)
            st.metric("Total Time", f"{minutes}m {seconds}s")
    
    with col2:
        st.metric("Output Directory", str(output_dir))
    
    # Show all prompts
    with st.expander("All Prompts Used", expanded=False):
        for i, prompt in enumerate(st.session_state.prompts, 1):
            st.text(f"Stage {i}: {prompt}")
    
    # Actions
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🆕 Generate Another Video", use_container_width=True, type="primary"):
            reset_session()
            st.rerun()
    
    with col2:
        if st.button("📂 Open Output Folder", use_container_width=True):
            st.info(f"Output saved to: {output_dir}")


def render_error():
    """Render the error screen."""
    st.header("❌ Error")
    
    st.error(st.session_state.error_message or "An unknown error occurred")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Retry Current Stage", use_container_width=True):
            st.session_state.status = "generating"
            st.session_state.current_prompt_id = None
            st.session_state.error_message = None
            st.rerun()
    
    with col2:
        if st.button("💾 Save Progress & Exit", use_container_width=True):
            if st.session_state.segment_paths:
                st.session_state.status = "complete"
                st.rerun()
            else:
                st.warning("No segments to save")
    
    with col3:
        if st.button("🆕 Start Over", use_container_width=True):
            reset_session()
            st.rerun()


def render_sidebar():
    """Render the sidebar with status and controls."""
    st.sidebar.title("Status")
    
    # Server status
    render_server_status()
    
    st.sidebar.divider()
    
    # Current session info
    if st.session_state.status != "idle":
        st.sidebar.subheader("Current Session")
        st.sidebar.text(f"Status: {st.session_state.status}")
        st.sidebar.text(f"Stage: {st.session_state.current_stage}/{st.session_state.total_stages}")
        st.sidebar.text(f"Segments: {len(st.session_state.segment_paths)}")
        
        if st.session_state.generation_start_time:
            elapsed = time.time() - st.session_state.generation_start_time
            st.sidebar.text(f"Elapsed: {elapsed:.0f}s")
    
    st.sidebar.divider()
    
    # Generation log
    if st.session_state.prompts:
        st.sidebar.subheader("Generation Log")
        for i, prompt in enumerate(st.session_state.prompts, 1):
            status_icon = "✓" if i < st.session_state.current_stage else ("⏳" if i == st.session_state.current_stage else "○")
            st.sidebar.text(f"{status_icon} Stage {i}: {prompt[:30]}...")
    
    st.sidebar.divider()
    
    # Quick actions
    st.sidebar.subheader("Quick Actions")
    
    if st.sidebar.button("🔄 Reset Session", use_container_width=True):
        reset_session()
        st.rerun()
    
    # ffmpeg status
    if check_ffmpeg_available():
        st.sidebar.success("✓ ffmpeg available")
    else:
        st.sidebar.error("✗ ffmpeg not found")


def main():
    """Main application entry point."""
    init_session_state()
    
    render_header()
    render_sidebar()
    
    # Route to appropriate view based on status
    status = st.session_state.status
    
    if status == "idle":
        render_configuration_form()
    elif status == "generating":
        render_generation_progress()
    elif status == "review":
        render_review_screen()
    elif status == "finalizing":
        render_finalizing()
    elif status == "complete":
        render_complete()
    elif status == "error":
        render_error()
    else:
        st.error(f"Unknown status: {status}")
        reset_session()
        st.rerun()


if __name__ == "__main__":
    main()
