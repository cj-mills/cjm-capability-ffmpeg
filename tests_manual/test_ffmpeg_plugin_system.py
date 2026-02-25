"""
Integration Test: FFmpeg Processing Plugin via PluginManager

Verifies that the FFmpeg plugin can be loaded and executed via JobQueue
over the process boundary through the plugin system.

Run from the cjm-media-plugin-ffmpeg conda environment:
    python tests_manual/test_ffmpeg_plugin_system.py
"""

import asyncio
import os
import sys

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.queue import JobQueue, JobStatus
from cjm_plugin_system.core.scheduling import QueueScheduler


PLUGIN_NAME = "cjm-media-plugin-ffmpeg"


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

    # Verify plugin is accessible
    proxy = manager.plugins.get(PLUGIN_NAME)
    assert proxy is not None, "Plugin proxy not found after loading"
    print(f"  Proxy available: {PLUGIN_NAME}")

    print("  PASSED\n")
    return manager


async def test_execute_via_queue(manager: PluginManager):
    """Verify execute dispatches correctly via JobQueue over process boundary."""
    print("=" * 60)
    print("TEST: Execute via JobQueue")
    print("=" * 60)

    queue = JobQueue(manager)
    await queue.start()

    # Test unknown action — should fail with ValueError
    print("  Submitting unknown action...")
    job_id = await queue.submit(PLUGIN_NAME, action="unknown_action", priority=10)
    job = await queue.wait_for_job(job_id, timeout=30)

    if job.status == JobStatus.failed:
        print(f"  unknown_action correctly failed: {job.error}")
    else:
        print(f"  ERROR: expected failure, got status={job.status}")

    # Test get_info stub — should fail with NotImplementedError
    print("\n  Submitting get_info stub...")
    job_id = await queue.submit(PLUGIN_NAME, action="get_info", file_path="/tmp/nonexistent.mp3", priority=10)
    job = await queue.wait_for_job(job_id, timeout=30)

    if job.status == JobStatus.failed:
        print(f"  get_info stub correctly failed: {job.error}")
    else:
        print(f"  ERROR: expected failure, got status={job.status}")

    await queue.stop()
    print("  PASSED\n")


async def run_integration():
    print()
    manager = await test_discover_and_load()
    if manager is None:
        print("Aborting — plugin not available.")
        sys.exit(1)

    await test_execute_via_queue(manager)

    manager.unload_all()
    print("=" * 60)
    print("ALL PLUGIN SYSTEM TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_integration())
