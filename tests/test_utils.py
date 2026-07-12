"""Tests for cjm_capability_ffmpeg.utils (c25780e8 flip).

Projected from the four utils notebooks' test cells; the segments check is
upgraded from the notebook's bare `callable` assert to a real stream-copy
round-trip on a generated tone (ffmpeg-on-PATH gated, no network)."""
import subprocess
from pathlib import Path

import pytest

from cjm_capability_ffmpeg.utils.availability import FFMPEG_AVAILABLE
from cjm_capability_ffmpeg.utils.codec import get_audio_codec
from cjm_capability_ffmpeg.utils.probe import get_media_duration
from cjm_capability_ffmpeg.utils.progress import parse_progress_line
from cjm_capability_ffmpeg.utils.segments import extract_audio_segment


def test_availability_flag_is_bool():
    assert isinstance(FFMPEG_AVAILABLE, bool)


def test_codec_map():
    assert get_audio_codec("mp3") == "libmp3lame"
    assert get_audio_codec("WAV") == "pcm_s16le"  # case-insensitive
    assert get_audio_codec("unknown-format") == "copy"


def test_probe_nonexistent_returns_none():
    assert get_media_duration(Path("/nonexistent/file.mp3")) is None


def test_parse_progress_line():
    assert parse_progress_line("out_time_ms=1000000") == 1.0
    assert parse_progress_line("time=00:00:02.50") == 2.5
    assert parse_progress_line("frame=10") is None


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg binary not on PATH")
def test_extract_audio_segment_round_trip(tmp_path):
    src = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-loglevel", "error", str(src)], check=True)
    out = tmp_path / "cut.wav"
    extract_audio_segment(src, out, start_time="0.5", duration="1.0")
    assert out.exists() and out.stat().st_size > 0
    dur = get_media_duration(out)
    assert dur is not None and 0.8 <= dur <= 1.2
