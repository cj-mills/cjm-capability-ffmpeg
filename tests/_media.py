"""Shared media fixtures for the ffmpeg capability tests (ffmpeg-on-PATH, no network)."""
import subprocess


def probe_stream_types(path):  # -> the codec_type of every stream in the file, in order
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def make_test_video(path, seconds=2.0):  # -> writes a tiny mpeg4+aac video at `path`
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"testsrc=size=64x64:rate=10:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(path)], check=True)
