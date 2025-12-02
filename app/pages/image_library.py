"""Image Library page for the Wan2.2 Video Generator app."""

import streamlit as st
from pathlib import Path


def render():
    """Render the image library page."""
    st.title("Image Library")
    st.caption("Manage your input images for video generation")
    
    st.divider()
    
    # Placeholder content
    st.info("The Image Library feature is coming soon!")
    
    st.markdown("""
    ### Planned Features
    
    This page will allow you to:
    
    - Upload and organize images for use as video generation inputs
    - Browse your image collection with thumbnails
    - Tag and categorize images
    - Select images directly when creating new jobs
    - View image metadata and history
    
    For now, you can upload images directly when creating a new job in the Job Queue.
    """)
    
    # Show any existing images in the output directories
    st.divider()
    st.subheader("Recent Input Images")
    
    output_dir = Path("output")
    images = []
    
    if output_dir.exists():
        for job_dir in output_dir.iterdir():
            if job_dir.is_dir():
                frames_dir = job_dir / "frames"
                if frames_dir.exists():
                    for img_file in frames_dir.glob("start_image.*"):
                        images.append({
                            "path": str(img_file),
                            "job": job_dir.name,
                            "name": img_file.name,
                        })
    
    if images:
        # Display images in a grid
        cols = st.columns(4)
        for i, img in enumerate(images[:12]):  # Show up to 12 images
            with cols[i % 4]:
                if Path(img["path"]).exists():
                    st.image(img["path"], caption=img["job"][:20], use_container_width=True)
    else:
        st.info("No input images found. Images will appear here after you create jobs.")
