"""Tests for cjm_capability_ffmpeg.utils (c25780e8 flip).

Projected from the four utils notebooks' test cells; the segments check is
upgraded from the notebook's bare `callable` assert to a real stream-copy
round-trip on a generated tone (ffmpeg-on-PATH gated, no network)."""
import subprocess
from pathlib import Path

import pytest

from cjm_capability_ffmpeg.utils.availability import FFMPEG_AVAILABLE
from cjm_capability_ffmpeg.utils.codec import get_audio_codec, get_audio_extension
from cjm_capability_ffmpeg.utils.probe import get_media_duration
from cjm_capability_ffmpeg.utils.progress import parse_progress_line
from cjm_capability_ffmpeg.utils.segments import extract_audio_segment

from _media import make_test_video, probe_stream_types


def test_availability_flag_is_bool():
    assert isinstance(FFMPEG_AVAILABLE, bool)


def test_codec_map():
    assert get_audio_codec("mp3") == "libmp3lame"
    assert get_audio_codec("WAV") == "pcm_s16le"  # case-insensitive
    assert get_audio_codec("unknown-format") == "copy"


def test_audio_extension_map():
    # ffprobe codec name -> the audio-only container that stream-copies it
    assert get_audio_extension("opus") == "ogg"
    assert get_audio_extension("AAC") == "m4a"  # case-insensitive
    assert get_audio_extension("pcm_s16le") == "wav"
    assert get_audio_extension("truehd") is None  # unmapped -> caller re-encodes
    assert get_audio_extension(None) is None


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


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg binary not on PATH")
def test_extract_audio_segment_drops_video_stream(tmp_path):
    # finding 63861c91: a VIDEO input must yield an AUDIO-ONLY segment — the
    # pre-guard cut copied the audio but re-encoded the video track per segment.
    src = tmp_path / "clip.mp4"
    make_test_video(src)
    assert probe_stream_types(src) == ["video", "audio"]
    out = tmp_path / "cut.m4a"
    extract_audio_segment(src, out, start_time="0.5", duration="1.0")
    assert probe_stream_types(out) == ["audio"]
    dur = get_media_duration(out)
    assert dur is not None and 0.8 <= dur <= 1.3
