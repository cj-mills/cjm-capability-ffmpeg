"""Extract temporal AUDIO segments from media files via ffmpeg stream-copy —
audio-only by contract (`-vn`): a video input yields an audio segment, never a
re-encoded video clip."""

import subprocess
from pathlib import Path

from cjm_capability_ffmpeg.utils.progress import run_ffmpeg_with_progress


def extract_audio_segment(input_path: Path,  # Path to the input media file (audio or video container)
                          output_path: Path,  # Path where the extracted audio segment is saved
                          start_time: str,  # Start time as "HH:MM:SS" or seconds
                          duration: str,  # Duration as "HH:MM:SS" or seconds
                          verbose: bool = False,  # If True, shows verbose ffmpeg output
                          pbar: bool = False,  # If True, shows a progress bar
                          copy_codec: bool = True,  # Stream-copy without re-encoding (fast)
                        ) -> None:  # Raises subprocess.CalledProcessError if extraction fails
    """Extract a temporal audio segment from a media file.

    Always drops the video stream (`-vn`): before this guard, a video input was
    cut with its video track re-encoded in software (VP9 via libvpx at well
    under real time), which is what made per-segment cuts of lecture recordings
    take ~10 minutes each (finding 63861c91). The output container must be an
    audio-only one that can hold the copied codec (see
    `cjm_capability_ffmpeg.utils.codec.get_audio_extension`)."""
    # Compute the expected segment duration for the progress bar.
    try:
        segment_duration = float(duration)
    except ValueError:
        time_parts = duration.split(':')
        if len(time_parts) == 3:
            hours = float(time_parts[0])
            minutes = float(time_parts[1])
            seconds = float(time_parts[2])
            segment_duration = hours * 3600 + minutes * 60 + seconds
        else:
            segment_duration = None

    # Two-stage seek. Input-side -ss (before -i) is the FAST seek: on a cluster-indexed
    # container (WebM/Matroska, MP4) it lands on the nearest cluster AT OR BEFORE the target,
    # and under stream copy every packet from there to the target is KEPT with a negative
    # timestamp — up to a cluster (~5 s) of audio before the requested start. The MP4 muxer
    # hides that behind an edit list; the Ogg muxer writes negative granule positions
    # ("Unsupported huge granule pos -192120") and ffmpeg-based readers (demucs, whisper,
    # torchaudio) decode ZERO samples while ffprobe still reports the full duration
    # (2026-09-10: demucs died on a bare assert over such a cut). `-avoid_negative_ts`
    # only relabels those packets — the segment would still start early against the spine.
    # The output-side `-ss 0` DROPS every packet before the (rebased) target, so the cut is
    # packet-accurate from `start_time` in any container, still without a decode: the real
    # 4K lecture cuts in 0.06 s and decodes to the requested length.
    cmd = [
        'ffmpeg',
        '-ss', start_time,
        '-i', str(input_path),
        '-ss', '0',
        '-t', duration,
        '-vn',
    ]
    if copy_codec:
        cmd.extend(['-acodec', 'copy'])
    cmd.extend(['-progress', 'pipe:2', '-y', str(output_path)])

    if pbar:
        run_ffmpeg_with_progress(
            cmd=cmd, total_duration=segment_duration,
            description="Extracting segment", verbose=verbose,
        )
    else:
        result = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd)
