"""Job Queue page for the Wan2.2 Video Generator app."""

import streamlit as st
from pathlib import Path
import json
import time
from datetime import datetime


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
    """Render the job queue table."""
    if not jobs:
        st.info("No jobs in the queue. Click 'New Job' to start generating videos!")
        return
    
    # Table header
    header_cols = st.columns([0.5, 2, 1.5, 1, 1, 1])
    with header_cols[0]:
        st.markdown("**#**")
    with header_cols[1]:
        st.markdown("**Name**")
    with header_cols[2]:
        st.markdown("**Start Time**")
    with header_cols[3]:
        st.markdown("**Status**")
    with header_cols[4]:
        st.markdown("**Progress**")
    with header_cols[5]:
        st.markdown("**Segments**")
    
    st.divider()
    
    # Table rows
    for i, job in enumerate(jobs):
        cols = st.columns([0.5, 2, 1.5, 1, 1, 1])
        
        with cols[0]:
            # Thumbnail or index
            if job["thumbnail"] and Path(job["thumbnail"]).exists():
                st.image(job["thumbnail"], width=40)
            else:
                st.markdown(f"{i + 1}")
        
        with cols[1]:
            # Clickable name
            if st.button(job["name"][:30], key=f"job_btn_{job['name']}", use_container_width=True):
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


def render_new_job_form():
    """Render the new job creation form."""
    st.subheader("Create New Job")
    
    # Back button
    if st.button("< Back to Job Queue"):
        st.session_state.show_new_job_form = False
        st.rerun()
    
    st.divider()
    
    st.info("New job creation form will be implemented here. For now, use the legacy generator.")
    
    # Link to legacy generator
    st.markdown("The full job creation workflow is available in the legacy generator (`wan_video_generator.py`).")


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
