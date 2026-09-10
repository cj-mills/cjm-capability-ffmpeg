"""Tests for cjm_capability_ffmpeg.capability (c25780e8 flip).

Projected from the capability notebook's five test cells: config schema,
identity/availability, initialize defaults + reconfigure, the stage-8 native
media-processing surface (no fused-era dispatcher), and the gone-field guards."""
import inspect
import subprocess

import pytest

from cjm_capability_ffmpeg.capability import (FFmpegCapabilityConfig,
                                              FFmpegProcessingCapability)
from cjm_capability_ffmpeg.utils.availability import FFMPEG_AVAILABLE
from cjm_capability_ffmpeg.utils.probe import get_media_duration
from cjm_substrate.utils.validation import dataclass_to_jsonschema

from _media import make_test_video, probe_stream_types


def test_config_schema_shape():
    schema = dataclass_to_jsonschema(FFmpegCapabilityConfig)
    assert "properties" in schema
    assert schema["properties"]["default_audio_format"]["default"] == "mp3"


def test_version_and_availability():
    cap = FFmpegProcessingCapability()
    assert isinstance(cap.version, str) and cap.version
    assert cap.is_available() == FFMPEG_AVAILABLE


def test_initialize_defaults_and_reconfigure():
    cap = FFmpegProcessingCapability()
    cap.initialize({})
    assert cap.config.default_audio_format == "mp3"
    assert cap.config.prefer_stream_copy is True
    assert cap.config.resampler == "soxr"
    assert not hasattr(cap, "storage")  # the adapter owns the cache (stage 8)

    cap.initialize({"default_audio_format": "wav", "default_audio_bitrate": "320k",
                    "resampler": "swr"})
    assert cap.config.default_audio_format == "wav"
    assert cap.config.default_audio_bitrate == "320k"
    assert cap.config.resampler == "swr"


def test_schema_has_no_fused_era_output_dir():
    cap = FFmpegProcessingCapability()
    cap.initialize({})
    props = cap.get_config_schema()["properties"]
    assert "output_dir" not in props  # the adapter chooses output location
    assert {"default_audio_format", "default_audio_bitrate",
            "prefer_stream_copy", "resampler"} <= set(props)


def test_native_media_processing_surface():
    cap = FFmpegProcessingCapability()
    for m in ("convert", "segment_audio", "extract_audio", "get_info",
              "get_current_config"):
        assert callable(getattr(cap, m, None)), f"missing native method {m}"
    # fused-era action dispatcher must be gone
    assert not hasattr(cap, "supported_actions")
    # extract_segment was dropped (no consumer; future HITL read is in-memory)
    assert not hasattr(cap, "extract_segment")
    assert "output_dir" in inspect.signature(cap.convert).parameters


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg binary not on PATH")
def test_segment_audio_on_video_is_audio_only(tmp_path):
    """finding 63861c91: cutting a VIDEO container yields audio-only segments in
    the codec's audio container (aac -> m4a), stream-copied — never `.mp4`
    clips with a re-encoded video track."""
    src = tmp_path / "lecture.mp4"
    make_test_video(src, seconds=3.0)
    cap = FFmpegProcessingCapability()
    cap.initialize({})
    result = cap.segment_audio(
        input_path=src, output_dir=str(tmp_path / "segs"),
        boundaries=[{"start": 0.0, "end": 1.0}, {"start": 1.0, "end": 2.5}],
    )
    assert result.segment_count == 2
    paths = [s.output_path for s in result.segments]
    assert all(p.endswith(".m4a") for p in paths), paths
    for p, expected in zip(paths, (1.0, 1.5)):
        assert probe_stream_types(p) == ["audio"]
        dur = get_media_duration(p)
        assert dur is not None and abs(dur - expected) <= 0.3


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg binary not on PATH")
def test_segment_audio_keeps_audio_only_input_extension(tmp_path):
    src = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=2", str(src)], check=True)
    cap = FFmpegProcessingCapability()
    cap.initialize({})
    result = cap.segment_audio(input_path=src, output_dir=str(tmp_path / "segs"),
                               boundaries=[{"start": 0.0, "end": 1.0}])
    assert result.segments[0].output_path.endswith(".wav")
    assert probe_stream_types(result.segments[0].output_path) == ["audio"]


def test_resolve_segment_format_policy(monkeypatch):
    cap = FFmpegProcessingCapability()
    cap.initialize({"default_audio_format": "mp3"})
    codecs = {"a.webm": "opus", "b.mkv": "truehd", "c.flac": "flac", "d.mp4": "aac"}
    monkeypatch.setattr(cap, "_detect_audio_codec", lambda p: codecs[p])
    assert cap._resolve_segment_format("a.webm", None) == ("ogg", True, "opus")   # video -> audio holder
    assert cap._resolve_segment_format("b.mkv", None) == ("mp3", False, "truehd")  # unmapped -> re-encode
    assert cap._resolve_segment_format("c.flac", None) == ("flac", True, "flac")   # audio-only keeps ext
    assert cap._resolve_segment_format("d.mp4", "wav") == ("wav", False, "aac")    # explicit wav re-encodes
    assert cap._resolve_segment_format("d.mp4", "m4a") == ("m4a", True, "aac")     # explicit match copies
