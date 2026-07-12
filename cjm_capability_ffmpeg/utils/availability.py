"""Detect whether the ffmpeg binary is installed on this system."""

import logging
import shutil

# Verify FFmpeg installation. True when the `ffmpeg` binary is on PATH.
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
if not FFMPEG_AVAILABLE:
    logging.warning(
        "FFmpeg not available - install the system package "
        "(e.g. apt install ffmpeg, brew install ffmpeg, or https://ffmpeg.org/)"
    )
