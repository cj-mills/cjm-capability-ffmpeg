# cjm-capability-ffmpeg

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

An FFmpeg-based media-processing capability for the cjm-substrate runtime that provides audio extraction, segmentation, and format conversion.

## Modules

- **`cjm_capability_ffmpeg.capability`** — FFmpeg-based media processing capability implementing the MediaProcessingCapability interface.
- **`cjm_capability_ffmpeg.utils.availability`** — Detect whether the ffmpeg binary is installed on this system.
- **`cjm_capability_ffmpeg.utils.codec`** — Map audio container formats to the ffmpeg codec used to encode them.
- **`cjm_capability_ffmpeg.utils.probe`** — Probe media files for metadata (duration, ...) via ffprobe.
- **`cjm_capability_ffmpeg.utils.progress`** — Run ffmpeg subprocess commands with a progress bar and optional callback.
- **`cjm_capability_ffmpeg.utils.segments`** — Extract temporal segments from audio files via ffmpeg stream-copy.

## API

### `cjm_capability_ffmpeg.capability`

- `FFmpegCapabilityConfig` _class_ — Configuration for the FFmpeg processing tool (the HOW knobs only).
- `FFmpegProcessingCapability` _class_ — FFmpeg-based media-processing tool capability (stage 8: pure compute).

### `cjm_capability_ffmpeg.utils.codec`

- `get_audio_codec` _function_ — Map an audio container format to the appropriate ffmpeg codec.

### `cjm_capability_ffmpeg.utils.probe`

- `get_media_duration` _function_ — Get the duration of a media file (seconds) via ffprobe.

### `cjm_capability_ffmpeg.utils.progress`

- `parse_progress_line` _function_ — Parse a progress line from ffmpeg stderr output.
- `run_ffmpeg_with_progress` _function_ — Run an ffmpeg command with a progress bar.

### `cjm_capability_ffmpeg.utils.segments`

- `extract_audio_segment` _function_ — Extract a temporal segment from an audio file.
