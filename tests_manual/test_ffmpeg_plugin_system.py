"""
Integration Test: FFmpeg Processing Plugin via PluginManager

Verifies that the FFmpeg plugin can be loaded and executed via JobQueue
over the process boundary through the plugin system.

Run from the cjm-media-plugin-ffmpeg conda environment:
    python tests_manual/test_ffmpeg_plugin_system.py
"""

import asyncio
import os
import shutil
import sys
import tempfile

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.queue import JobQueue, JobStatus
from cjm_plugin_system.core.scheduling import QueueScheduler


PLUGIN_NAME = "cjm-media-plugin-ffmpeg"
TEST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_files")
SAMPLE_AUDIO = os.path.join(TEST_DIR, "sample_audio.mp3")
SAMPLE_VIDEO = os.path.join(TEST_DIR, "sample_video.mp4")


def _reload_plugin(manager: PluginManager, config: dict = None):
    """Unload, re-discover, and reload the plugin with the given config."""
    manager.unload_all()
    manager.discover_manifests()
    plugin_meta = next(item for item in manager.discovered if item.name == PLUGIN_NAME)
    manager.load_plugin(plugin_meta, config or {})


async def test_discover_and_load():
    """Verify the plugin is discovered and loads via PluginManager."""
    print("=" * 60)
    print("TEST: Discover and Load via PluginManager")
    print("=" * 60)

    manager = PluginManager(scheduler=QueueScheduler())
    manager.discover_manifests()

    plugin_meta = next((item for item in manager.discovered if item.name == PLUGIN_NAME), None)
    if not plugin_meta:
        print(f"  Plugin {PLUGIN_NAME} not found in discovered manifests.")
        print("  Have you run 'cjm-ctl install' for this plugin?")
        return None
    print(f"  Discovered: {plugin_meta.name} v{plugin_meta.version}")

    if not manager.load_plugin(plugin_meta, {}):
        print("  Failed to load plugin.")
        return None
    print("  Loaded successfully")

    proxy = manager.plugins.get(PLUGIN_NAME)
    assert proxy is not None, "Plugin proxy not found after loading"
    print(f"  Proxy available: {PLUGIN_NAME}")

    print("  PASSED\n")
    return manager


async def test_get_info_via_queue(manager: PluginManager):
    """Verify get_info works via JobQueue over process boundary."""
    print("=" * 60)
    print("TEST: get_info via JobQueue")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    queue = JobQueue(manager)
    await queue.start()

    job_id = await queue.submit(PLUGIN_NAME, action="get_info", file_path=SAMPLE_AUDIO, priority=10)
    job = await queue.wait_for_job(job_id, timeout=30)

    assert job.status == JobStatus.completed, f"Expected completed, got {job.status}: {job.error}"
    result = job.result
    assert isinstance(result, dict)
    assert result["path"] == SAMPLE_AUDIO
    assert result["duration"] > 0
    assert result["size_bytes"] > 0
    assert len(result["audio_streams"]) >= 1
    print(f"  Duration: {result['duration']:.1f}s")
    print(f"  Format: {result['format']}")
    print(f"  Audio codec: {result['audio_streams'][0]['codec']}")

    # Test missing file — should fail
    job_id = await queue.submit(PLUGIN_NAME, action="get_info", file_path="/tmp/nonexistent.mp3", priority=10)
    job = await queue.wait_for_job(job_id, timeout=30)
    assert job.status == JobStatus.failed
    print(f"  Missing file correctly failed")

    await queue.stop()
    print("  PASSED\n")


async def test_extract_segment_via_queue(manager: PluginManager):
    """Verify extract_segment works via JobQueue over process boundary."""
    print("=" * 60)
    print("TEST: extract_segment via JobQueue")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_ps_test_")
    try:
        _reload_plugin(manager, {"output_dir": tmp_dir})

        queue = JobQueue(manager)
        await queue.start()

        job_id = await queue.submit(
            PLUGIN_NAME,
            action="extract_segment",
            input_path=SAMPLE_AUDIO, start=5.0, end=20.0,
            priority=10
        )
        job = await queue.wait_for_job(job_id, timeout=60)

        assert job.status == JobStatus.completed, f"Expected completed, got {job.status}: {job.error}"
        result = job.result
        assert "output_path" in result
        assert os.path.exists(result["output_path"])
        print(f"  Output: {os.path.basename(result['output_path'])}")
        print(f"  File exists: True")

        await queue.stop()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def test_extract_audio_via_queue(manager: PluginManager):
    """Verify extract_audio works via JobQueue over process boundary."""
    print("=" * 60)
    print("TEST: extract_audio via JobQueue")
    print("=" * 60)

    if not os.path.exists(SAMPLE_VIDEO):
        print(f"  SKIPPED — {SAMPLE_VIDEO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_ps_test_")
    try:
        _reload_plugin(manager, {"output_dir": tmp_dir})

        queue = JobQueue(manager)
        await queue.start()

        job_id = await queue.submit(
            PLUGIN_NAME,
            action="extract_audio",
            input_path=SAMPLE_VIDEO,
            priority=10
        )
        job = await queue.wait_for_job(job_id, timeout=60)

        assert job.status == JobStatus.completed, f"Expected completed, got {job.status}: {job.error}"
        result = job.result
        assert "output_path" in result
        assert "job_id" in result
        assert "codec" in result
        assert "stream_copy" in result
        assert os.path.exists(result["output_path"])
        print(f"  Output: {os.path.basename(result['output_path'])}")
        print(f"  Codec: {result['codec']}")
        print(f"  Stream copy: {result['stream_copy']}")
        print(f"  Duration: {result['duration']:.1f}s")

        await queue.stop()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def test_segment_audio_via_queue(manager: PluginManager):
    """Verify segment_audio works via JobQueue over process boundary."""
    print("=" * 60)
    print("TEST: segment_audio via JobQueue")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_ps_test_")
    try:
        _reload_plugin(manager, {"output_dir": tmp_dir})

        queue = JobQueue(manager)
        await queue.start()

        boundaries = [
            {"start": 0.0, "end": 30.0},
            {"start": 30.0, "end": 60.0},
            {"start": 60.0, "end": 90.0},
        ]

        job_id = await queue.submit(
            PLUGIN_NAME,
            action="segment_audio",
            input_path=SAMPLE_AUDIO,
            boundaries=boundaries,
            priority=10
        )
        job = await queue.wait_for_job(job_id, timeout=120)

        assert job.status == JobStatus.completed, f"Expected completed, got {job.status}: {job.error}"
        result = job.result
        assert result["segment_count"] == 3
        assert "batch_key" in result
        assert len(result["segments"]) == 3

        print(f"  Segments: {result['segment_count']}")
        print(f"  Batch key: {result['batch_key'][:8]}...")
        for seg in result["segments"]:
            assert os.path.exists(seg["output_path"])
            print(f"    Segment {seg['index']}: [{seg['start']:.1f}-{seg['end']:.1f}]"
                  f" -> {os.path.basename(seg['output_path'])}")

        await queue.stop()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def test_unknown_action_via_queue(manager: PluginManager):
    """Verify unknown action fails correctly via JobQueue."""
    print("=" * 60)
    print("TEST: Unknown action via JobQueue")
    print("=" * 60)

    _reload_plugin(manager)

    queue = JobQueue(manager)
    await queue.start()

    job_id = await queue.submit(PLUGIN_NAME, action="unknown_action", priority=10)
    job = await queue.wait_for_job(job_id, timeout=30)

    assert job.status == JobStatus.failed
    print(f"  Correctly failed: {job.error}")

    await queue.stop()
    print("  PASSED\n")


async def run_integration():
    print()
    manager = await test_discover_and_load()
    if manager is None:
        print("Aborting — plugin not available.")
        sys.exit(1)

    await test_get_info_via_queue(manager)
    await test_extract_segment_via_queue(manager)
    await test_extract_audio_via_queue(manager)
    await test_segment_audio_via_queue(manager)
    await test_unknown_action_via_queue(manager)

    manager.unload_all()
    print("=" * 60)
    print("ALL PLUGIN SYSTEM TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_integration())
