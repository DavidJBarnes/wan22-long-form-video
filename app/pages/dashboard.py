"""Dashboard page for the Wan2.2 Video Generator app."""

import streamlit as st
import requests
import subprocess
from pathlib import Path
import json


def check_comfyui_connection(server_url: str) -> tuple[bool, str]:
    """Check if the ComfyUI server is reachable.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        response = requests.get(f"{server_url}/system_stats", timeout=10)
        if response.status_code == 200:
            return True, "Connected"
        return False, f"Error: Status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, f"Error: {str(e)}"


def check_ffmpeg_available() -> tuple[bool, str]:
    """Check if ffmpeg is available on the system.
    
    Returns:
        Tuple of (available, version_or_message)
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Extract version from first line
            version_line = result.stdout.split('\n')[0]
            return True, version_line
        return False, "ffmpeg not working properly"
    except FileNotFoundError:
        return False, "ffmpeg not found"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg check timed out"
    except Exception as e:
        return False, f"Error: {str(e)}"


def get_jobs_summary() -> list[dict]:
    """Get summary of recent jobs from the output directory.
    
    Returns:
        List of job info dicts
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
                    
                    jobs.append({
                        "name": job_dir.name,
                        "path": str(job_dir),
                        "status": state.get("status", "unknown"),
                        "current_stage": state.get("current_stage", 0),
                        "total_stages": state.get("total_stages", 0),
                        "start_time": state.get("generation_start_time"),
                        "thumbnail": thumbnail,
                        "num_segments": len(state.get("segment_paths", [])),
                    })
                except Exception:
                    continue
    
    return jobs[:10]  # Return last 10 jobs


def render():
    """Render the dashboard page."""
    st.title("Dashboard")
    st.caption("Overview of your video generation system")
    
    # Get settings
    app_settings = st.session_state.get("app_settings", {})
    server_url = app_settings.get("comfyui_server_url", "http://3090.zero:8188")
    
    # Status cards row
    col1, col2 = st.columns(2)
    
    # ComfyUI Server Status Card
    with col1:
        st.subheader("ComfyUI Server")
        
        connected, status_msg = check_comfyui_connection(server_url)
        
        with st.container(border=True):
            st.markdown(f"**Server URL:** `{server_url}`")
            
            if connected:
                st.markdown(f"**Status:** :green[{status_msg}]")
            else:
                st.markdown(f"**Status:** :red[{status_msg}]")
                st.warning("Server not connected. Check your settings.")
                if st.button("Go to Settings", key="goto_settings_comfyui"):
                    st.session_state.current_page = "Settings"
                    st.rerun()
    
    # ffmpeg Status Card
    with col2:
        st.subheader("ffmpeg")
        
        ffmpeg_available, ffmpeg_msg = check_ffmpeg_available()
        
        with st.container(border=True):
            if ffmpeg_available:
                st.markdown(f"**Status:** :green[Available]")
                st.caption(ffmpeg_msg[:60] + "..." if len(ffmpeg_msg) > 60 else ffmpeg_msg)
            else:
                st.markdown(f"**Status:** :red[Not Available]")
                st.warning(ffmpeg_msg)
                st.info("ffmpeg is required for video concatenation. Please install it on your system.")
    
    st.divider()
    
    # Job Queue Preview
    st.subheader("Recent Jobs")
    
    # New Job button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("+ New Job", type="primary", use_container_width=True):
            st.session_state.current_page = "Job Queue"
            st.session_state.show_new_job_form = True
            st.rerun()
    
    # Jobs table
    jobs = get_jobs_summary()
    
    if jobs:
        # Create a table-like display
        for job in jobs[:5]:  # Show top 5 on dashboard
            with st.container(border=True):
                cols = st.columns([1, 3, 2, 2, 2])
                
                # Thumbnail
                with cols[0]:
                    if job["thumbnail"] and Path(job["thumbnail"]).exists():
                        st.image(job["thumbnail"], width=60)
                    else:
                        st.markdown("🎬")
                
                # Name (clickable to view job details)
                with cols[1]:
                    if st.button(job['name'][:25], key=f"dash_job_{job['name']}"):
                        st.session_state.selected_job = job
                        st.session_state.show_job_detail = True
                        st.session_state.current_page = "Job Queue"
                        st.rerun()
                
                # Status with color
                with cols[2]:
                    status = job["status"]
                    status_colors = {
                        "complete": "green",
                        "generating": "orange",
                        "review": "blue",
                        "error": "red",
                        "idle": "gray",
                    }
                    color = status_colors.get(status, "gray")
                    st.markdown(f":{color}[{status}]")
                
                # Progress
                with cols[3]:
                    st.markdown(f"Stage {job['current_stage']}/{job['total_stages']}")
                
                # Segments
                with cols[4]:
                    st.markdown(f"{job['num_segments']} segments")
        
        # Link to full job queue
        if len(jobs) > 5:
            if st.button("View All Jobs", use_container_width=True):
                st.session_state.current_page = "Job Queue"
                st.rerun()
    else:
        st.info("No jobs found. Click 'New Job' to start generating videos!")
