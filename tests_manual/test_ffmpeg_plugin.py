"""Manual integration test for the FFmpeg processing plugin.

Run from the cjm-media-plugin-ffmpeg conda environment:
    python tests_manual/test_ffmpeg_plugin.py
"""

import os
import shutil
import sys
import tempfile

from cjm_media_plugin_ffmpeg.meta import get_plugin_metadata
from cjm_media_plugin_ffmpeg.plugin import FFmpegPluginConfig, FFmpegProcessingPlugin
from cjm_plugin_system.utils.validation import dataclass_to_jsonschema

# Test files
TEST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_files")
SAMPLE_AUDIO = os.path.join(TEST_DIR, "sample_audio.mp3")
SAMPLE_VIDEO = os.path.join(TEST_DIR, "sample_video.mp4")


def test_metadata():
    """Verify plugin metadata is correct."""
    print("=" * 60)
    print("TEST: Plugin Metadata")
    print("=" * 60)

    meta = get_plugin_metadata()
    assert meta["name"] == "cjm-media-plugin-ffmpeg"
    assert meta["type"] == "media-processing"
    assert meta["category"] == "media"
    assert meta["interface"].endswith("MediaProcessingPlugin")
    assert meta["class"] == "FFmpegProcessingPlugin"
    assert meta["module"] == "cjm_media_plugin_ffmpeg.plugin"
    assert "db_path" in meta
    assert meta["resources"]["requires_gpu"] is False

    print(f"  Name: {meta['name']}")
    print(f"  Version: {meta['version']}")
    print(f"  Type: {meta['type']}")
    print(f"  DB path: {meta['db_path']}")
    print("  PASSED\n")


def test_config_schema():
    """Verify config dataclass and JSON schema generation."""
    print("=" * 60)
    print("TEST: Config Schema")
    print("=" * 60)

    schema = dataclass_to_jsonschema(FFmpegPluginConfig)
    props = schema["properties"]

    assert "output_dir" in props
    assert "default_audio_format" in props
    assert "default_audio_bitrate" in props
    assert "prefer_stream_copy" in props

    assert props["default_audio_format"]["default"] == "mp3"
    assert props["default_audio_bitrate"]["default"] == "192k"
    assert props["prefer_stream_copy"]["default"] is True

    assert "enum" in props["default_audio_format"]
    assert "mp3" in props["default_audio_format"]["enum"]

    print(f"  Properties: {list(props.keys())}")
    print(f"  Default format: {props['default_audio_format']['default']}")
    print(f"  Format options: {props['default_audio_format']['enum']}")
    print("  PASSED\n")


def test_plugin_lifecycle():
    """Verify plugin instantiation, initialization, and cleanup."""
    print("=" * 60)
    print("TEST: Plugin Lifecycle")
    print("=" * 60)

    plugin = FFmpegProcessingPlugin()
    assert plugin.name == "ffmpeg"
    assert plugin.version == "1.0.0"
    assert plugin.supported_media_types == ["audio", "video"]
    print(f"  Created: {plugin.name} v{plugin.version}")

    plugin.initialize({})
    assert plugin.config is not None
    assert plugin.config.default_audio_format == "mp3"
    assert plugin.storage is not None
    print(f"  Initialized with defaults: {plugin.get_current_config()}")

    plugin.initialize({"default_audio_format": "wav", "default_audio_bitrate": "320k"})
    assert plugin.config.default_audio_format == "wav"
    assert plugin.config.default_audio_bitrate == "320k"
    print(f"  Re-initialized with custom: {plugin.get_current_config()}")

    schema = plugin.get_config_schema()
    assert "properties" in schema
    print(f"  Schema properties: {list(schema['properties'].keys())}")

    available = plugin.is_available()
    print(f"  FFmpeg available: {available}")

    plugin.cleanup()
    print("  Cleanup complete")
    print("  PASSED\n")


def test_execute_stubs():
    """Verify execute dispatcher raises NotImplementedError for Phase 3 stubs."""
    print("=" * 60)
    print("TEST: Execute Stubs (Phase 3)")
    print("=" * 60)

    plugin = FFmpegProcessingPlugin()
    plugin.initialize({})

    stub_actions = [
        ("extract_audio", {"input_path": "/tmp/test.mp4"}),
        ("segment_audio", {"input_path": "/tmp/test.mp3", "boundaries": []}),
    ]

    for action, kwargs in stub_actions:
        try:
            plugin.execute(action=action, **kwargs)
            print(f"  {action}: ERROR — should have raised NotImplementedError")
            sys.exit(1)
        except NotImplementedError:
            print(f"  {action}: correctly raises NotImplementedError")

    # Unknown action should raise ValueError
    try:
        plugin.execute(action="unknown_action")
        print("  unknown_action: ERROR — should have raised ValueError")
        sys.exit(1)
    except ValueError as e:
        print(f"  unknown_action: correctly raises ValueError ('{e}')")

    plugin.cleanup()
    print("  PASSED\n")


def test_get_info_audio():
    """Verify get_info returns correct metadata for an audio file."""
    print("=" * 60)
    print("TEST: get_info (audio)")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    plugin = FFmpegProcessingPlugin()
    plugin.initialize({})

    info = plugin.get_info(SAMPLE_AUDIO)
    assert info.path == SAMPLE_AUDIO
    assert info.duration > 0
    assert info.size_bytes > 0
    assert len(info.audio_streams) >= 1
    assert info.audio_streams[0]["codec"] is not None

    print(f"  Path: {os.path.basename(info.path)}")
    print(f"  Duration: {info.duration:.1f}s ({info.duration/60:.1f} min)")
    print(f"  Size: {info.size_bytes / 1024 / 1024:.1f} MB")
    print(f"  Format: {info.format}")
    print(f"  Audio streams: {len(info.audio_streams)}")
    print(f"  Audio codec: {info.audio_streams[0]['codec']}")
    if info.video_streams:
        print(f"  Video streams: {len(info.video_streams)} (cover art)")

    # Test via execute dispatcher
    result = plugin.execute(action="get_info", file_path=SAMPLE_AUDIO)
    assert result["duration"] == info.duration
    assert result["path"] == SAMPLE_AUDIO
    print("  Execute dispatch: OK")

    plugin.cleanup()
    print("  PASSED\n")


def test_get_info_video():
    """Verify get_info returns correct metadata for a video file."""
    print("=" * 60)
    print("TEST: get_info (video)")
    print("=" * 60)

    if not os.path.exists(SAMPLE_VIDEO):
        print(f"  SKIPPED — {SAMPLE_VIDEO} not found\n")
        return

    plugin = FFmpegProcessingPlugin()
    plugin.initialize({})

    info = plugin.get_info(SAMPLE_VIDEO)
    assert info.path == SAMPLE_VIDEO
    assert info.duration > 0
    assert info.size_bytes > 0
    assert len(info.video_streams) >= 1
    assert len(info.audio_streams) >= 1
    assert info.video_streams[0]["codec"] is not None
    assert info.audio_streams[0]["codec"] is not None

    print(f"  Path: {os.path.basename(info.path)}")
    print(f"  Duration: {info.duration:.1f}s ({info.duration/60:.1f} min)")
    print(f"  Size: {info.size_bytes / 1024 / 1024:.1f} MB")
    print(f"  Format: {info.format}")
    print(f"  Video streams: {len(info.video_streams)}")
    print(f"  Video codec: {info.video_streams[0]['codec']}")
    print(f"  Resolution: {info.video_streams[0].get('width')}x{info.video_streams[0].get('height')}")
    print(f"  Audio streams: {len(info.audio_streams)}")
    print(f"  Audio codec: {info.audio_streams[0]['codec']}")

    plugin.cleanup()
    print("  PASSED\n")


def test_get_info_missing_file():
    """Verify get_info raises FileNotFoundError for missing files."""
    print("=" * 60)
    print("TEST: get_info (missing file)")
    print("=" * 60)

    plugin = FFmpegProcessingPlugin()
    plugin.initialize({})

    try:
        plugin.get_info("/tmp/nonexistent_file.mp3")
        print("  ERROR — should have raised FileNotFoundError")
        sys.exit(1)
    except FileNotFoundError:
        print("  Correctly raises FileNotFoundError")

    plugin.cleanup()
    print("  PASSED\n")


def test_convert():
    """Verify convert produces a valid output file in the target format."""
    print("=" * 60)
    print("TEST: convert")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_test_")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        output_path = plugin.convert(SAMPLE_AUDIO, "wav", bitrate="128k")
        assert os.path.exists(output_path), f"Output file not created: {output_path}"
        assert output_path.endswith(".wav")

        # Verify output is valid audio
        info = plugin.get_info(output_path)
        assert info.duration > 0
        assert len(info.audio_streams) >= 1
        print(f"  Input: {os.path.basename(SAMPLE_AUDIO)}")
        print(f"  Output: {os.path.basename(output_path)}")
        print(f"  Output duration: {info.duration:.1f}s")
        print(f"  Output size: {info.size_bytes / 1024 / 1024:.1f} MB")
        print(f"  Output codec: {info.audio_streams[0]['codec']}")

        # Verify job was stored
        jobs = plugin.storage.list_jobs(limit=1)
        assert len(jobs) == 1
        assert jobs[0].action == "convert"
        assert jobs[0].input_path == SAMPLE_AUDIO
        assert jobs[0].output_path == output_path
        print(f"  Job stored: {jobs[0].job_id[:8]}...")

        # Verify via execute dispatcher
        result = plugin.execute(action="convert", input_path=SAMPLE_AUDIO, output_format="wav")
        assert "output_path" in result
        print("  Execute dispatch: OK")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_extract_segment():
    """Verify extract_segment produces a correct time-bounded segment."""
    print("=" * 60)
    print("TEST: extract_segment")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_test_")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        start, end = 10.0, 25.0
        expected_duration = end - start

        output_path = plugin.extract_segment(SAMPLE_AUDIO, start, end)
        assert os.path.exists(output_path), f"Output file not created: {output_path}"

        # Verify output duration is approximately correct
        info = plugin.get_info(output_path)
        assert abs(info.duration - expected_duration) < 1.0, \
            f"Duration mismatch: expected ~{expected_duration}s, got {info.duration:.2f}s"
        print(f"  Input: {os.path.basename(SAMPLE_AUDIO)}")
        print(f"  Segment: [{start:.1f}s - {end:.1f}s]")
        print(f"  Output: {os.path.basename(output_path)}")
        print(f"  Output duration: {info.duration:.2f}s (expected ~{expected_duration:.1f}s)")

        # Verify job was stored
        jobs = plugin.storage.list_jobs(limit=1)
        assert len(jobs) == 1
        assert jobs[0].action == "extract_segment"
        print(f"  Job stored: {jobs[0].job_id[:8]}...")

        # Test with custom output path
        custom_output = os.path.join(tmp_dir, "custom_segment.mp3")
        output_path2 = plugin.extract_segment(SAMPLE_AUDIO, 5.0, 10.0, output_path=custom_output)
        assert output_path2 == custom_output
        assert os.path.exists(custom_output)
        print(f"  Custom output path: OK")

        # Test invalid range
        try:
            plugin.extract_segment(SAMPLE_AUDIO, 10.0, 5.0)
            print("  ERROR — should have raised ValueError for end < start")
            sys.exit(1)
        except ValueError:
            print("  Invalid range correctly rejected")

        # Verify via execute dispatcher
        result = plugin.execute(action="extract_segment", input_path=SAMPLE_AUDIO, start=0.0, end=5.0)
        assert "output_path" in result
        print("  Execute dispatch: OK")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_metadata()
    test_config_schema()
    test_plugin_lifecycle()
    test_execute_stubs()
    test_get_info_audio()
    test_get_info_video()
    test_get_info_missing_file()
    test_convert()
    test_extract_segment()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
