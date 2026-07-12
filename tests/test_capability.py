"""Tests for cjm_capability_ffmpeg.capability (c25780e8 flip).

Projected from the capability notebook's five test cells: config schema,
identity/availability, initialize defaults + reconfigure, the stage-8 native
media-processing surface (no fused-era dispatcher), and the gone-field guards."""
import inspect

from cjm_capability_ffmpeg.capability import (FFmpegCapabilityConfig,
                                              FFmpegProcessingCapability)
from cjm_capability_ffmpeg.utils.availability import FFMPEG_AVAILABLE
from cjm_substrate.utils.validation import dataclass_to_jsonschema


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
