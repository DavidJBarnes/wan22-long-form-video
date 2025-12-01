"""Video utilities for frame extraction and video concatenation."""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import cv2


def extract_last_frame(video_path: Path, output_path: Path) -> tuple[bool, str]:
    """Extract the last frame from a video file.
    
    Args:
        video_path: Path to the input video file
        output_path: Path where the extracted frame should be saved
        
    Returns:
        Tuple of (success, message)
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            return False, f"Could not open video file: {video_path}"
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames <= 0:
            cap.release()
            return False, "Video has no frames"
        
        # Seek to the last frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return False, "Could not read the last frame"
        
        # Convert BGR to RGB for saving
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Save as PNG for lossless quality
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
        
        return True, f"Extracted last frame to {output_path}"
        
    except Exception as e:
        return False, f"Error extracting frame: {str(e)}"


def get_video_info(video_path: Path) -> dict:
    """Get information about a video file.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Dictionary with video info (fps, frame_count, width, height, duration)
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            return {}
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        cap.release()
        
        duration = frame_count / fps if fps > 0 else 0
        
        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration": duration
        }
        
    except Exception:
        return {}


def concatenate_videos(
    segment_paths: list[Path],
    output_path: Path,
    fps: int = 16
) -> tuple[bool, str]:
    """Concatenate multiple video segments into a single video.
    
    Uses ffmpeg for reliable concatenation with the concat demuxer.
    
    Args:
        segment_paths: List of paths to video segments in order
        output_path: Path for the output concatenated video
        fps: Target frames per second
        
    Returns:
        Tuple of (success, message)
    """
    if not segment_paths:
        return False, "No video segments provided"
    
    # Verify all segments exist
    for path in segment_paths:
        if not path.exists():
            return False, f"Segment not found: {path}"
    
    try:
        # Create a temporary concat list file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            concat_file = Path(f.name)
            for path in segment_paths:
                # Use absolute paths and escape single quotes
                abs_path = str(path.absolute()).replace("'", "'\\''")
                f.write(f"file '{abs_path}'\n")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Run ffmpeg concat
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',  # Copy streams without re-encoding
            str(output_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Clean up concat file
        concat_file.unlink()
        
        if result.returncode == 0:
            return True, f"Successfully concatenated {len(segment_paths)} segments to {output_path}"
        else:
            return False, f"ffmpeg error: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return False, "Video concatenation timed out"
    except FileNotFoundError:
        return False, "ffmpeg not found. Please install ffmpeg."
    except Exception as e:
        return False, f"Error concatenating videos: {str(e)}"


def concatenate_videos_reencode(
    segment_paths: list[Path],
    output_path: Path,
    fps: int = 16
) -> tuple[bool, str]:
    """Concatenate videos with re-encoding (use if copy mode fails).
    
    This is slower but more reliable for videos with different codecs/parameters.
    
    Args:
        segment_paths: List of paths to video segments in order
        output_path: Path for the output concatenated video
        fps: Target frames per second
        
    Returns:
        Tuple of (success, message)
    """
    if not segment_paths:
        return False, "No video segments provided"
    
    try:
        # Create a temporary concat list file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            concat_file = Path(f.name)
            for path in segment_paths:
                abs_path = str(path.absolute()).replace("'", "'\\''")
                f.write(f"file '{abs_path}'\n")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Run ffmpeg with re-encoding
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-r', str(fps),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for re-encoding
        )
        
        concat_file.unlink()
        
        if result.returncode == 0:
            return True, f"Successfully concatenated {len(segment_paths)} segments to {output_path}"
        else:
            return False, f"ffmpeg error: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return False, "Video concatenation timed out"
    except FileNotFoundError:
        return False, "ffmpeg not found. Please install ffmpeg."
    except Exception as e:
        return False, f"Error concatenating videos: {str(e)}"


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system.
    
    Returns:
        True if ffmpeg is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False
