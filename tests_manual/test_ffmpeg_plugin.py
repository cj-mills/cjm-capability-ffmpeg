"""Manual integration test for the FFmpeg processing plugin.

Run from the cjm-media-plugin-ffmpeg conda environment:
    python tests_manual/test_ffmpeg_plugin.py
"""

import os
import shutil
import sys
import tempfile
import time

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


def test_unknown_action():
    """Verify unknown action raises ValueError."""
    print("=" * 60)
    print("TEST: Unknown Action")
    print("=" * 60)

    plugin = FFmpegProcessingPlugin()
    plugin.initialize({})

    try:
        plugin.execute(action="unknown_action")
        print("  ERROR — should have raised ValueError")
        sys.exit(1)
    except ValueError as e:
        print(f"  Correctly raises ValueError ('{e}')")

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

        info = plugin.get_info(output_path)
        assert info.duration > 0
        assert len(info.audio_streams) >= 1
        print(f"  Input: {os.path.basename(SAMPLE_AUDIO)}")
        print(f"  Output: {os.path.basename(output_path)}")
        print(f"  Output duration: {info.duration:.1f}s")
        print(f"  Output size: {info.size_bytes / 1024 / 1024:.1f} MB")
        print(f"  Output codec: {info.audio_streams[0]['codec']}")

        jobs = plugin.storage.list_jobs(limit=1)
        assert len(jobs) == 1
        assert jobs[0].action == "convert"
        print(f"  Job stored: {jobs[0].job_id[:8]}...")

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
        assert os.path.exists(output_path)

        info = plugin.get_info(output_path)
        assert abs(info.duration - expected_duration) < 1.0
        print(f"  Segment: [{start:.1f}s - {end:.1f}s]")
        print(f"  Output duration: {info.duration:.2f}s (expected ~{expected_duration:.1f}s)")

        jobs = plugin.storage.list_jobs(limit=1)
        assert len(jobs) == 1
        assert jobs[0].action == "extract_segment"
        print(f"  Job stored: {jobs[0].job_id[:8]}...")

        # Test invalid range
        try:
            plugin.extract_segment(SAMPLE_AUDIO, 10.0, 5.0)
            print("  ERROR — should have raised ValueError")
            sys.exit(1)
        except ValueError:
            print("  Invalid range correctly rejected")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_extract_audio():
    """Verify extract_audio extracts audio from video via stream copy."""
    print("=" * 60)
    print("TEST: extract_audio")
    print("=" * 60)

    if not os.path.exists(SAMPLE_VIDEO):
        print(f"  SKIPPED — {SAMPLE_VIDEO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_test_")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        t_start = time.time()
        result = plugin.execute(action="extract_audio", input_path=SAMPLE_VIDEO)
        elapsed = time.time() - t_start

        assert "output_path" in result
        assert "job_id" in result
        assert "duration" in result
        assert "codec" in result
        assert "stream_copy" in result
        assert os.path.exists(result["output_path"])

        # Verify output is valid audio
        info = plugin.get_info(result["output_path"])
        assert info.duration > 0
        assert len(info.audio_streams) >= 1

        print(f"  Input: {os.path.basename(SAMPLE_VIDEO)}")
        print(f"  Output: {os.path.basename(result['output_path'])}")
        print(f"  Codec: {result['codec']}")
        print(f"  Stream copy: {result['stream_copy']}")
        print(f"  Duration: {result['duration']:.1f}s")
        print(f"  Output size: {info.size_bytes / 1024 / 1024:.1f} MB")
        print(f"  Elapsed: {elapsed:.1f}s")

        # Stream copy should be fast (well under the file duration)
        if result["stream_copy"]:
            assert elapsed < result["duration"] / 10, \
                f"Stream copy too slow: {elapsed:.1f}s for {result['duration']:.1f}s file"
            print(f"  Speed check: OK (stream copy is fast)")

        # Verify job was stored
        jobs = plugin.storage.list_jobs(limit=1)
        assert len(jobs) == 1
        assert jobs[0].action == "extract_audio"
        print(f"  Job stored: {jobs[0].job_id[:8]}...")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_extract_audio_with_format():
    """Verify extract_audio with explicit output format triggers re-encoding."""
    print("=" * 60)
    print("TEST: extract_audio (with output_format)")
    print("=" * 60)

    if not os.path.exists(SAMPLE_VIDEO):
        print(f"  SKIPPED — {SAMPLE_VIDEO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_test_")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        # Request MP3 from AAC video — should re-encode
        result = plugin.execute(action="extract_audio", input_path=SAMPLE_VIDEO, output_format="mp3")
        assert os.path.exists(result["output_path"])
        assert result["output_path"].endswith(".mp3")
        assert result["stream_copy"] is False

        info = plugin.get_info(result["output_path"])
        assert info.duration > 0
        print(f"  Output: {os.path.basename(result['output_path'])}")
        print(f"  Stream copy: {result['stream_copy']} (re-encoded to mp3)")
        print(f"  Output size: {info.size_bytes / 1024 / 1024:.1f} MB")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_segment_audio():
    """Verify segment_audio splits audio at specified boundaries."""
    print("=" * 60)
    print("TEST: segment_audio")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_test_")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        boundaries = [
            {"start": 0.0, "end": 30.0},
            {"start": 30.0, "end": 60.0},
            {"start": 60.0, "end": 90.0},
        ]

        result = plugin.execute(action="segment_audio", input_path=SAMPLE_AUDIO, boundaries=boundaries)
        assert result["segment_count"] == 3
        assert result["input_path"] == SAMPLE_AUDIO
        assert "batch_key" in result
        assert len(result["segments"]) == 3

        print(f"  Input: {os.path.basename(SAMPLE_AUDIO)}")
        print(f"  Segments: {result['segment_count']}")
        print(f"  Total duration: {result['total_duration']:.1f}s")
        print(f"  Batch key: {result['batch_key'][:8]}...")

        for seg in result["segments"]:
            assert os.path.exists(seg["output_path"])
            info = plugin.get_info(seg["output_path"])
            expected = seg["end"] - seg["start"]
            assert abs(info.duration - expected) < 1.0
            print(f"    Segment {seg['index']}: [{seg['start']:.1f}-{seg['end']:.1f}]"
                  f" -> {os.path.basename(seg['output_path'])} ({info.duration:.2f}s)")

        # Verify all jobs stored with correct batch_key
        batch_key = result["batch_key"]
        jobs = plugin.storage.list_jobs(limit=100)
        segment_jobs = [j for j in jobs if j.action == "segment_audio"
                        and j.parameters.get("batch_key") == batch_key]
        assert len(segment_jobs) == 3, \
            f"Expected 3 jobs for batch_key, got {len(segment_jobs)}"
        print(f"  All jobs share batch_key: OK")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_segment_audio_validation():
    """Verify segment_audio rejects invalid boundaries."""
    print("=" * 60)
    print("TEST: segment_audio (validation)")
    print("=" * 60)

    plugin = FFmpegProcessingPlugin()
    plugin.initialize({})

    # Empty boundaries
    try:
        plugin.execute(action="segment_audio", input_path=SAMPLE_AUDIO, boundaries=[])
        print("  ERROR — should have raised ValueError for empty boundaries")
        sys.exit(1)
    except ValueError:
        print("  Empty boundaries correctly rejected")

    # Inverted boundary
    try:
        plugin.execute(action="segment_audio", input_path=SAMPLE_AUDIO,
                       boundaries=[{"start": 10.0, "end": 5.0}])
        print("  ERROR — should have raised ValueError for inverted boundary")
        sys.exit(1)
    except ValueError:
        print("  Inverted boundary correctly rejected")

    # Overlapping boundaries
    try:
        plugin.execute(action="segment_audio", input_path=SAMPLE_AUDIO,
                       boundaries=[{"start": 0.0, "end": 20.0}, {"start": 15.0, "end": 30.0}])
        print("  ERROR — should have raised ValueError for overlap")
        sys.exit(1)
    except ValueError:
        print("  Overlapping boundaries correctly rejected")

    # Missing file
    try:
        plugin.execute(action="segment_audio", input_path="/tmp/nonexistent.mp3",
                       boundaries=[{"start": 0.0, "end": 10.0}])
        print("  ERROR — should have raised FileNotFoundError")
        sys.exit(1)
    except FileNotFoundError:
        print("  Missing file correctly rejected")

    plugin.cleanup()
    print("  PASSED\n")


def test_segment_audio_custom_template():
    """Verify segment_audio respects custom filename_template."""
    print("=" * 60)
    print("TEST: segment_audio (custom template)")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_test_")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        boundaries = [
            {"start": 0.0, "end": 15.0},
            {"start": 15.0, "end": 30.0},
        ]

        result = plugin.execute(
            action="segment_audio", input_path=SAMPLE_AUDIO,
            boundaries=boundaries, filename_template="chunk_{index:04d}"
        )

        for seg in result["segments"]:
            basename = os.path.basename(seg["output_path"])
            assert basename.startswith("chunk_"), f"Expected 'chunk_' prefix, got '{basename}'"
            print(f"    {basename}")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_metadata()
    test_config_schema()
    test_plugin_lifecycle()
    test_unknown_action()
    test_get_info_audio()
    test_get_info_video()
    test_get_info_missing_file()
    test_convert()
    test_extract_segment()
    test_extract_audio()
    test_extract_audio_with_format()
    test_segment_audio()
    test_segment_audio_validation()
    test_segment_audio_custom_template()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
