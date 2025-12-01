# Wan2.2 Long Video Generator

A Streamlit web application for generating long-form videos using the Wan2.2 14B I2V model by chaining multiple short video segments together with seamless transitions.

## Features

- Multi-stage video generation with manual review between stages
- Automatic last-frame extraction for seamless transitions
- Two-pass sampling (high_noise + low_noise models) for quality
- Real-time progress tracking and generation logs
- Video concatenation with ffmpeg
- Session state management for reliable operation

## Requirements

- Python 3.10+
- ffmpeg installed and available in PATH
- Access to a ComfyUI server with Wan2.2 models loaded
- Required Python packages (see requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/DavidJBarnes/wan22-workflows.git
cd wan22-workflows/app
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
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

## Configuration

Edit `config.py` to configure:

- `COMFYUI_SERVER_URL`: URL of your ComfyUI server (default: `http://3090.zero:8188`)
- `DEFAULT_WIDTH`, `DEFAULT_HEIGHT`: Default video resolution
- `DEFAULT_FPS`: Default frames per second
- Model names and paths
- Generation parameters

## ComfyUI Server Setup

Ensure your ComfyUI server has the following models installed:

**Diffusion Models** (place in `models/diffusion_models/`):
- `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`
- `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`

**VAE** (place in `models/vae/`):
- `wan_2.1_vae.safetensors`

**Text Encoder** (place in `models/text_encoders/`):
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors`

Download models from: https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged

## Usage

1. Start the Streamlit app:
```bash
streamlit run wan_video_generator.py
```

2. Open your browser to `http://localhost:8501`

3. Configure your video:
   - Set total duration (in seconds)
   - Set resolution (default 640x640)
   - Set FPS (default 16)
   - Choose segment duration (3, 4, or 5 seconds)
   - Enter output filename

4. Upload a start image (this will be the first frame)

5. Enter your initial prompt describing the first segment

6. Click "Start Generation"

7. After each stage completes:
   - Review the last frame (this becomes the next stage's start)
   - Enter a prompt for the next stage
   - Click "Continue" to proceed or "Regenerate" to retry

8. After all stages complete, click "Finalize Video" to concatenate segments

## Workflow

```
┌─────────────────┐
│ Configuration   │
│ - Duration      │
│ - Resolution    │
│ - Start Image   │
│ - Initial Prompt│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Stage 1         │◄──────────────┐
│ - Upload image  │               │
│ - Generate      │               │
│ - Extract frame │               │
└────────┬────────┘               │
         │                        │
         ▼                        │
┌─────────────────┐               │
│ Review          │               │
│ - View frame    │               │
│ - Enter prompt  │               │
│ - Continue/     │───────────────┘
│   Regenerate    │  (next stage)
└────────┬────────┘
         │ (all stages done)
         ▼
┌─────────────────┐
│ Finalize        │
│ - Concatenate   │
│ - Save video    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Complete        │
│ - Download      │
│ - View summary  │
└─────────────────┘
```

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

## Troubleshooting

### Cannot connect to ComfyUI server
- Verify the server URL in `config.py`
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

## API Reference

### ComfyUI Endpoints Used

- `POST /prompt` - Queue a workflow for execution
- `GET /history/{prompt_id}` - Check execution status
- `GET /view?filename={name}` - Download output files
- `POST /upload/image` - Upload input images
- `GET /system_stats` - Check server status
- `GET /queue` - Get queue status

## License

MIT License - See LICENSE file for details.
