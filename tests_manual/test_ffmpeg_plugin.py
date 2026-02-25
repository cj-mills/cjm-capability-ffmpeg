"""Manual integration test for the FFmpeg processing plugin.

Run from the cjm-media-plugin-ffmpeg conda environment:
    python tests_manual/test_ffmpeg_plugin.py
"""

import sys

from cjm_media_plugin_ffmpeg.meta import get_plugin_metadata
from cjm_media_plugin_ffmpeg.plugin import FFmpegPluginConfig, FFmpegProcessingPlugin
from cjm_plugin_system.utils.validation import dataclass_to_jsonschema


def test_metadata():
    """Verify plugin metadata is correct."""
    print("=" * 60)
    print("TEST: Plugin Metadata")
    print("=" * 60)

    meta = get_plugin_metadata()
    assert meta["name"] == "cjm-media-plugin-ffmpeg", f"Expected name 'cjm-media-plugin-ffmpeg', got '{meta['name']}'"
    assert meta["type"] == "media-processing", f"Expected type 'media-processing', got '{meta['type']}'"
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

    # Initialize with defaults
    plugin.initialize({})
    assert plugin.config is not None
    assert plugin.config.default_audio_format == "mp3"
    assert plugin.config.default_audio_bitrate == "192k"
    assert plugin.config.prefer_stream_copy is True
    assert plugin.storage is not None
    print(f"  Initialized with defaults: {plugin.get_current_config()}")

    # Initialize with custom config
    plugin.initialize({"default_audio_format": "wav", "default_audio_bitrate": "320k"})
    assert plugin.config.default_audio_format == "wav"
    assert plugin.config.default_audio_bitrate == "320k"
    print(f"  Re-initialized with custom: {plugin.get_current_config()}")

    # Config schema
    schema = plugin.get_config_schema()
    assert "properties" in schema
    print(f"  Schema properties: {list(schema['properties'].keys())}")

    # Availability
    available = plugin.is_available()
    print(f"  FFmpeg available: {available}")

    # Cleanup
    plugin.cleanup()
    print("  Cleanup complete")
    print("  PASSED\n")


def test_execute_stubs():
    """Verify execute dispatcher raises NotImplementedError for unimplemented actions."""
    print("=" * 60)
    print("TEST: Execute Stubs")
    print("=" * 60)

    plugin = FFmpegProcessingPlugin()
    plugin.initialize({})

    actions_to_test = [
        ("get_info", {"file_path": "/tmp/test.mp3"}),
        ("convert", {"input_path": "/tmp/test.mp3", "output_format": "wav"}),
        ("extract_segment", {"input_path": "/tmp/test.mp3", "start": 0.0, "end": 1.0}),
        ("extract_audio", {"input_path": "/tmp/test.mp4"}),
        ("segment_audio", {"input_path": "/tmp/test.mp3", "boundaries": []}),
    ]

    for action, kwargs in actions_to_test:
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


if __name__ == "__main__":
    test_metadata()
    test_config_schema()
    test_plugin_lifecycle()
    test_execute_stubs()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
