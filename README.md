# Multi-Stage Video Generation with Wan2.2 14B I2V

This repository contains ComfyUI workflows for generating long-form videos using the Wan2.2 14B Image-to-Video model by chaining multiple video segments together.

## Overview

The workflow generates videos by creating multiple 3-5 second segments, where each segment uses the last frame of the previous segment as its starting point. This ensures seamless character and scene continuity throughout the final video.

## Workflows Included

1. **multi_stage_video_wan2_2_14B_i2v.json** - Main workflow for generating individual video segments
2. **video_concatenation_workflow.json** - Workflow for combining all segments into a final video

## Hardware Requirements

- GPU: RTX 3090 or better (24GB VRAM recommended)
- The workflow uses fp8 quantized models to fit within 24GB VRAM

## Required Models

Download all models from [Hugging Face](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged) and place them in the appropriate directories:

### Diffusion Models (models/diffusion_models/)
- `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`
- `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`

### VAE (models/vae/)
- `wan_2.1_vae.safetensors`

### Text Encoder (models/text_encoders/)
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors`

## How to Use

### Stage-by-Stage Generation

1. **Load the workflow**: Open `multi_stage_video_wan2_2_14B_i2v.json` in ComfyUI

2. **Configure video settings** in the "Video Size & Length" (WanImageToVideo) node:
   - Width/Height: 640x640 (default, adjust based on VRAM)
   - Length: Number of frames per segment
     - 81 frames = 5.0 seconds
     - 65 frames = 4.0 seconds
     - 49 frames = 3.0 seconds
     - 33 frames = 2.0 seconds

3. **Stage 1 - Initial Generation**:
   - Load your starting image in the "Start Image" node
   - Enter your prompt for the first segment in the "Positive Prompt" node
   - Queue the workflow

4. **Review and Continue**:
   - After generation completes, review the output video
   - Check the "Preview Last Frame" node to see the starting point for the next segment
   - The last frame is automatically saved to `output/multi_stage_video/last_frame_*.png`

5. **Stage 2+ - Subsequent Generations**:
   - Load the saved last frame as your new start image
   - Enter a new prompt describing what should happen next
   - Queue the workflow again

6. **Regenerate** (if needed):
   - Keep the same start image loaded
   - Modify your prompt if desired
   - Re-queue the workflow

### Combining Segments

1. **Load the concatenation workflow**: Open `video_concatenation_workflow.json` in ComfyUI

2. **Load your segments**: Update the file paths in each LoadVideo node to point to your generated segments (found in `output/multi_stage_video/`)

3. **Add more segments** if needed:
   - Add additional LoadVideo nodes for each segment
   - Add ConcatVideo nodes to chain them together
   - Connect the output of the previous ConcatVideo to the first input of the new one

4. **Queue the workflow** to generate the final concatenated video

## Generation Parameters

The workflow uses proven parameters from the reference workflow:

### Two-Pass Sampling
- **Pass 1 (High Noise Model)**:
  - Steps: 20
  - CFG: 3.5
  - Sampler: euler
  - Scheduler: simple
  - Start step: 0, End step: 10
  - Add noise: enabled

- **Pass 2 (Low Noise Model)**:
  - Steps: 20
  - CFG: 3.5
  - Sampler: euler
  - Scheduler: simple
  - Start step: 10, End step: 10000
  - Add noise: disabled

### Model Configuration
- ModelSamplingSD3 shift value: 8.0 (for both models)

## Output Files

All output files are saved to `ComfyUI/output/multi_stage_video/`:
- `segment_*.mp4` - Individual video segments
- `last_frame_*.png` - Last frames for seamless transitions
- `final_output_*.mp4` - Concatenated final video (from concatenation workflow)

## Tips for Best Results

1. **Seamless Transitions**: The workflow automatically extracts and saves the last frame of each segment. Always use this saved frame as the start image for the next segment.

2. **Prompt Continuity**: Write prompts that describe the continuation of the scene. Reference what's visible in the last frame preview.

3. **Consistent Style**: Keep your negative prompt consistent across all stages to maintain visual style.

4. **VRAM Management**: If you encounter VRAM issues, reduce the resolution or frame count in the WanImageToVideo node.

5. **Planning**: Calculate the number of stages needed before starting:
   - 30-second video at 5s segments = 6 stages
   - 60-second video at 5s segments = 12 stages

## Segment Duration Reference

| Frames | Duration (at 16 FPS) |
|--------|---------------------|
| 81     | 5.0 seconds         |
| 65     | 4.0 seconds         |
| 49     | 3.0 seconds         |
| 33     | 2.0 seconds         |

## Troubleshooting

- **Out of VRAM**: Reduce resolution (try 512x512) or reduce frame count
- **Poor transitions**: Ensure you're using the exact last frame from the previous segment
- **Inconsistent style**: Check that your negative prompt is consistent across stages
- **Model not found**: Verify models are in the correct directories with exact filenames

## Dependencies

- ComfyUI (latest version recommended)
- No additional custom nodes required - uses built-in ComfyUI nodes only
