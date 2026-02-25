"""
Phase 4 Integration Test: Realistic segmentation with VAD boundaries,
edge cases, and provenance chain verification.

Run from the cjm-media-plugin-ffmpeg conda environment:
    python tests_manual/test_ffmpeg_integration.py
"""

import json
import os
import shutil
import sys
import tempfile
import time

from cjm_media_plugin_ffmpeg.plugin import FFmpegProcessingPlugin

# Test files
TEST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_files")
SAMPLE_AUDIO = os.path.join(TEST_DIR, "sample_audio.mp3")
SAMPLE_VIDEO = os.path.join(TEST_DIR, "sample_video.mp4")
SAMPLE_VAD = os.path.join(TEST_DIR, "sample_audio_vad.json")


# ------------------------------------------------------------------
# Boundary computation helper (mirrors what the service layer will do)
# ------------------------------------------------------------------

def compute_segment_boundaries(vad_ranges, audio_duration, max_segment_duration=600.0):
    """Group VAD chunks into segments of ~max_segment_duration seconds.

    Places cut points at the midpoint of silence gaps between groups.
    First segment starts at 0.0, last segment ends at audio_duration.
    """
    if not vad_ranges:
        return [{"start": 0.0, "end": audio_duration}]

    boundaries = []
    group_start_idx = 0
    accumulated = 0.0

    for i, chunk in enumerate(vad_ranges):
        chunk_duration = chunk["end"] - chunk["start"]
        accumulated += chunk_duration

        is_last = (i == len(vad_ranges) - 1)

        if accumulated >= max_segment_duration or is_last:
            if is_last:
                # Last group — end at audio duration
                seg_end = audio_duration
            else:
                # Cut at midpoint of silence gap between this chunk and next
                gap_start = chunk["end"]
                gap_end = vad_ranges[i + 1]["start"]
                seg_end = (gap_start + gap_end) / 2.0

            # Segment start: 0.0 for first, previous cut point for rest
            seg_start = boundaries[-1]["end"] if boundaries else 0.0

            boundaries.append({"start": seg_start, "end": seg_end})
            group_start_idx = i + 1
            accumulated = 0.0

    return boundaries


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_vad_segmentation():
    """Test realistic segmentation using pre-computed VAD boundaries."""
    print("=" * 60)
    print("TEST: VAD-based segmentation (4.5hr podcast)")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO) or not os.path.exists(SAMPLE_VAD):
        print(f"  SKIPPED — test files not found\n")
        return

    # Load VAD ranges
    with open(SAMPLE_VAD) as f:
        vad_ranges = json.load(f)
    print(f"  VAD chunks loaded: {len(vad_ranges)}")

    # Get audio duration
    plugin = FFmpegProcessingPlugin()
    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_int_test_")

    try:
        plugin.initialize({"output_dir": tmp_dir})
        info = plugin.get_info(SAMPLE_AUDIO)
        audio_duration = info.duration
        print(f"  Audio duration: {audio_duration:.1f}s ({audio_duration/60:.1f} min)")

        # Compute boundaries (~10 min segments)
        boundaries = compute_segment_boundaries(vad_ranges, audio_duration, max_segment_duration=600.0)
        print(f"  Computed boundaries: {len(boundaries)} segments")

        # Verify boundaries are contiguous
        assert boundaries[0]["start"] == 0.0, "First segment must start at 0.0"
        assert abs(boundaries[-1]["end"] - audio_duration) < 0.1, \
            f"Last segment end ({boundaries[-1]['end']}) must match audio duration ({audio_duration})"
        for i in range(1, len(boundaries)):
            assert abs(boundaries[i]["start"] - boundaries[i-1]["end"]) < 0.001, \
                f"Gap between segment {i-1} and {i}"
        print("  Boundary contiguity: OK")

        # Run segmentation
        t_start = time.time()
        result = plugin.execute(
            action="segment_audio",
            input_path=SAMPLE_AUDIO,
            boundaries=boundaries,
        )
        elapsed = time.time() - t_start

        assert result["segment_count"] == len(boundaries)
        assert len(result["segments"]) == len(boundaries)
        print(f"  Segmentation complete: {result['segment_count']} segments in {elapsed:.1f}s")
        print(f"  Batch key: {result['batch_key'][:8]}...")

        # Verify all segments exist and have reasonable durations
        for seg in result["segments"]:
            assert os.path.exists(seg["output_path"]), f"Missing: {seg['output_path']}"
            expected = seg["end"] - seg["start"]
            seg_info = plugin.get_info(seg["output_path"])
            assert abs(seg_info.duration - expected) < 2.0, \
                f"Segment {seg['index']}: expected ~{expected:.1f}s, got {seg_info.duration:.1f}s"

        # Print summary table
        print(f"\n  {'Idx':>4}  {'Start':>10}  {'End':>10}  {'Duration':>10}  {'File':>20}")
        print(f"  {'---':>4}  {'-----':>10}  {'---':>10}  {'--------':>10}  {'----':>20}")
        for seg in result["segments"][:5]:
            dur = seg["end"] - seg["start"]
            print(f"  {seg['index']:>4}  {seg['start']:>10.1f}  {seg['end']:>10.1f}"
                  f"  {dur:>10.1f}  {os.path.basename(seg['output_path']):>20}")
        if len(result["segments"]) > 5:
            print(f"  {'...':>4}")
            seg = result["segments"][-1]
            dur = seg["end"] - seg["start"]
            print(f"  {seg['index']:>4}  {seg['start']:>10.1f}  {seg['end']:>10.1f}"
                  f"  {dur:>10.1f}  {os.path.basename(seg['output_path']):>20}")

        # Verify jobs in database (filter by this run's batch_key)
        batch_key = result["batch_key"]
        jobs = plugin.storage.list_jobs(limit=1000)
        seg_jobs = [j for j in jobs if j.action == "segment_audio"
                    and j.parameters.get("batch_key") == batch_key]
        assert len(seg_jobs) == len(boundaries), \
            f"Expected {len(boundaries)} jobs for batch_key, got {len(seg_jobs)}"
        print(f"\n  Database jobs: {len(seg_jobs)} (batch_key={batch_key[:8]}...)")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_edge_single_segment():
    """Test audio shorter than max segment duration (single segment)."""
    print("=" * 60)
    print("TEST: Edge case — single segment")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_int_test_")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        # Single boundary covering first 30 seconds
        result = plugin.execute(
            action="segment_audio",
            input_path=SAMPLE_AUDIO,
            boundaries=[{"start": 0.0, "end": 30.0}],
        )

        assert result["segment_count"] == 1
        assert len(result["segments"]) == 1
        assert os.path.exists(result["segments"][0]["output_path"])
        print(f"  Single segment: {os.path.basename(result['segments'][0]['output_path'])}")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_edge_auto_create_output_dir():
    """Test that nested output directories are auto-created."""
    print("=" * 60)
    print("TEST: Edge case — auto-create output dir")
    print("=" * 60)

    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  SKIPPED — {SAMPLE_AUDIO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_int_test_")
    nested_dir = os.path.join(tmp_dir, "deep", "nested", "dir")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": nested_dir})

        result = plugin.execute(
            action="extract_segment",
            input_path=SAMPLE_AUDIO,
            start=0.0, end=5.0,
        )

        assert os.path.exists(result["output_path"])
        print(f"  Output in nested dir: {result['output_path']}")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_edge_corrupted_input():
    """Test error handling for corrupted/invalid input files."""
    print("=" * 60)
    print("TEST: Edge case — corrupted input")
    print("=" * 60)

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_int_test_")
    try:
        # Create a fake file that isn't valid media
        fake_file = os.path.join(tmp_dir, "fake.mp3")
        with open(fake_file, "w") as f:
            f.write("this is not an mp3 file")

        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        # get_info should fail on corrupted file
        try:
            plugin.get_info(fake_file)
            print("  ERROR — get_info should have failed on corrupted file")
            sys.exit(1)
        except Exception as e:
            print(f"  get_info correctly failed: {type(e).__name__}")

        # extract_segment should fail on corrupted file
        try:
            plugin.extract_segment(fake_file, 0.0, 5.0)
            print("  ERROR — extract_segment should have failed on corrupted file")
            sys.exit(1)
        except Exception as e:
            print(f"  extract_segment correctly failed: {type(e).__name__}")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_provenance_chain():
    """Test that job records enable full provenance chain reconstruction."""
    print("=" * 60)
    print("TEST: Provenance chain (video → audio → segments)")
    print("=" * 60)

    if not os.path.exists(SAMPLE_VIDEO):
        print(f"  SKIPPED — {SAMPLE_VIDEO} not found\n")
        return

    tmp_dir = tempfile.mkdtemp(prefix="ffmpeg_int_test_")
    try:
        plugin = FFmpegProcessingPlugin()
        plugin.initialize({"output_dir": tmp_dir})

        # Step 1: Extract audio from video
        extract_result = plugin.execute(action="extract_audio", input_path=SAMPLE_VIDEO)
        extracted_audio = extract_result["output_path"]
        print(f"  1. Extracted: {os.path.basename(extracted_audio)}")

        # Step 2: Segment the extracted audio
        boundaries = [
            {"start": 0.0, "end": 60.0},
            {"start": 60.0, "end": 120.0},
        ]
        segment_result = plugin.execute(
            action="segment_audio",
            input_path=extracted_audio,
            boundaries=boundaries,
        )
        print(f"  2. Segmented: {segment_result['segment_count']} segments")

        # Reconstruct provenance chain from database
        jobs = plugin.storage.list_jobs(limit=100)

        # Find extraction job
        extract_jobs = [j for j in jobs if j.action == "extract_audio"]
        assert len(extract_jobs) >= 1
        extract_job = extract_jobs[0]
        assert extract_job.input_path == SAMPLE_VIDEO
        print(f"\n  Provenance chain:")
        print(f"    Source: {os.path.basename(extract_job.input_path)}")
        print(f"      → extract_audio (job {extract_job.job_id[:8]}...)")
        print(f"      → {os.path.basename(extract_job.output_path)}")

        # Find segment jobs linked to the extracted audio
        seg_jobs = [j for j in jobs if j.action == "segment_audio"
                    and j.input_path == extracted_audio]
        assert len(seg_jobs) == 2
        batch_key = seg_jobs[0].parameters["batch_key"]
        for sj in sorted(seg_jobs, key=lambda j: j.parameters["index"]):
            assert sj.parameters["batch_key"] == batch_key
            print(f"        → segment_audio #{sj.parameters['index']}"
                  f" (job {sj.job_id[:8]}...)"
                  f" → {os.path.basename(sj.output_path)}")

        # Verify hashes enable integrity checking
        extract_input_ok = plugin.storage.verify_input(extract_job.job_id)
        extract_output_ok = plugin.storage.verify_output(extract_job.job_id)
        assert extract_input_ok is True, "Extract input hash mismatch"
        assert extract_output_ok is True, "Extract output hash mismatch"
        print(f"\n  Hash verification:")
        print(f"    Extract input hash: OK")
        print(f"    Extract output hash: OK")

        seg_output_ok = plugin.storage.verify_output(seg_jobs[0].job_id)
        assert seg_output_ok is True, "Segment output hash mismatch"
        print(f"    Segment 0 output hash: OK")

        plugin.cleanup()
        print("  PASSED\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_vad_segmentation()
    test_edge_single_segment()
    test_edge_auto_create_output_dir()
    test_edge_corrupted_input()
    test_provenance_chain()
    print("=" * 60)
    print("ALL INTEGRATION TESTS PASSED")
    print("=" * 60)
