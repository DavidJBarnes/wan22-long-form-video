# Wan2.2 Long Video Generator

A Streamlit web application for generating long-form videos using the Wan2.2 14B I2V model by chaining multiple short video segments together with seamless transitions.

## Features

- Multi-page navigation with Dashboard, Job Queue, Image Library, and Settings
- Real-time ComfyUI server status monitoring
- Job queue management with detailed job views
- Multi-stage video generation with manual review between stages
- Automatic last-frame extraction for seamless transitions
- Two-pass sampling (high_noise + low_noise models) for quality
- LoRA support for model fine-tuning (optional)
- Video concatenation with ffmpeg
- Persistent settings configuration

## Requirements

- Python 3.12 (recommended)
- ffmpeg installed and available in PATH
- Access to a ComfyUI server with Wan2.2 models loaded
- Required Python packages (see requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/DavidJBarnes/wan22-workflows.git
cd wan22-workflows/app
```

2. Create a virtual environment with Python 3.12:
```bash
# Using Python 3.12 specifically
python3.12 -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On Linux/macOS
# OR
venv\Scripts\activate     # On Windows
```

If you don't have Python 3.12 installed:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv

# macOS with Homebrew
brew install python@3.12

# Then create venv with:
python3.12 -m venv venv
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Ensure ffmpeg is installed:
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows - download from https://ffmpeg.org/download.html
```

## Running the Application

Start the new multi-page Streamlit app:
```bash
streamlit run app.py
```

Or run the legacy single-page generator:
```bash
streamlit run wan_video_generator.py
```

Open your browser to `http://localhost:8501`

## Application Pages

### Dashboard
- Overview of your video generation system
- ComfyUI server connection status with color indicators
- ffmpeg availability check
- Recent jobs preview with quick access

### Job Queue
- Table view of all jobs with status, progress, and thumbnails
- Detailed job view showing sequence timeline
- View generated segments and prompts
- Create new jobs

### Image Library
- Browse and manage input images (coming soon)
- View recent input images from past jobs

### Settings
- Configure ComfyUI server URL
- Set default generation parameters (width, height, FPS, frames per segment)
- Edit model configurations (JSON format)
- Configure generation parameters for two-pass sampling
- Set default negative prompt
- Configure segment duration options

## Configuration

Settings can be configured through the Settings page in the app, or by editing `config.py` directly:

- `COMFYUI_SERVER_URL`: URL of your ComfyUI server (default: `http://3090.zero:8188`)
- `DEFAULT_WIDTH`, `DEFAULT_HEIGHT`: Default video resolution (default: 640x640)
- `DEFAULT_FPS`: Default frames per second (default: 16)
- `DEFAULT_FRAMES_PER_SEGMENT`: Default frames per segment (default: 81)
- Model names and paths
- Generation parameters for two-pass sampling
- Segment duration options

## ComfyUI Server Setup

Ensure your ComfyUI server has the following models installed:

**Diffusion Models** (place in `models/diffusion_models/`):
- `wan2.2_i2v_high_noise_14B_fp16.safetensors`
- `wan2.2_i2v_low_noise_14B_fp16.safetensors`

**VAE** (place in `models/vae/`):
- `wan_2.1_vae.safetensors`

**Text Encoder** (place in `models/text_encoders/`):
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors`

Download models from: https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged

## Output Files

Generated files are saved to the `output/` directory:

```
output/
└── {filename}_{timestamp}/
    ├── segments/
    │   ├── segment_001.mp4
    │   ├── segment_002.mp4
    │   └── ...
    ├── frames/
    │   ├── start_image.png
    │   ├── frame_001.png
    │   ├── frame_002.png
    │   └── ...
    ├── job_state.json
    └── {filename}_final.mp4
```

## Generation Parameters

The app uses two-pass sampling for high-quality generation:

**First Pass (High Noise Model)**:
- Steps: 20
- CFG: 3.5
- Sampler: euler
- Scheduler: simple
- Start step: 0, End step: 10

**Second Pass (Low Noise Model)**:
- Steps: 20
- CFG: 3.5
- Sampler: euler
- Scheduler: simple
- Start step: 10, End step: 10000

## LoRA Support

The app supports optional LoRA models for fine-tuning:
- Select a LoRA for the high noise model (first pass)
- Select a LoRA for the low noise model (second pass)
- LoRAs are queried dynamically from your ComfyUI server

## Troubleshooting

### Cannot connect to ComfyUI server
- Check the server URL in Settings
- Ensure ComfyUI is running and accessible
- Check firewall settings

### Generation fails or times out
- Check ComfyUI server logs for errors
- Verify all required models are loaded
- Try reducing resolution or frame count
- Check available VRAM (requires ~20GB for 640x640)

### Video concatenation fails
- Ensure ffmpeg is installed and in PATH
- Check that all segment files exist
- Try the re-encoding fallback (automatic)

### ffmpeg not found
- Install ffmpeg using your system's package manager
- Verify it's in your PATH: `ffmpeg -version`

### Python version issues
- This app is tested with Python 3.12
- Create a virtual environment with the correct Python version
- Ensure you activate the venv before running

## API Reference

### ComfyUI Endpoints Used

- `POST /prompt` - Queue a workflow for execution
- `GET /history/{prompt_id}` - Check execution status
- `GET /view?filename={name}` - Download output files
- `POST /upload/image` - Upload input images
- `GET /system_stats` - Check server status
- `GET /queue` - Get queue status
- `GET /object_info` - Get available LoRAs and node info

## License

MIT License - See LICENSE file for details.
