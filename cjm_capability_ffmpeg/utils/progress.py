"""Run ffmpeg subprocess commands with a progress bar and optional callback."""

import subprocess
from typing import Callable, List, Optional

from tqdm.auto import tqdm


def parse_progress_line(line: str  # A line of stderr output from ffmpeg
                        ) -> Optional[float]:  # Current time in seconds, or None if the line has no progress info
    """Parse a progress line from ffmpeg stderr output."""
    # Look for time progress in the format "out_time_ms=123456789"
    if line.startswith('out_time_ms='):
        try:
            time_ms = int(line.strip().split('=')[1])
            return time_ms / 1000000.0  # microseconds -> seconds
        except (ValueError, IndexError):
            pass
    # Alternative: look for time in the format "time=00:01:23.45"
    elif line.startswith('time='):
        try:
            time_str = line.strip().split('=')[1]
            time_parts = time_str.split(':')
            if len(time_parts) == 3:
                hours = float(time_parts[0])
                minutes = float(time_parts[1])
                seconds = float(time_parts[2])
                return hours * 3600 + minutes * 60 + seconds
        except (ValueError, IndexError):
            pass
    return None


def run_ffmpeg_with_progress(
    cmd: List[str],  # The ffmpeg command and arguments
    total_duration: Optional[float] = None,  # Total duration in seconds for a determinate bar, else indeterminate
    description: str = "Processing",  # Description text for the progress bar
    verbose: bool = False,  # If True, prints detailed ffmpeg output
    progress_callback: Optional[Callable[[float], None]] = None  # Optional callback receiving current progress in seconds
) -> None:  # Raises FileNotFoundError or subprocess.CalledProcessError on failure
    """Run an ffmpeg command with a progress bar."""
    try:
        if total_duration:
            pbar = tqdm(
                total=total_duration, unit='s', desc=description,
                bar_format='{l_bar}{bar}| {n:.1f}/{total:.1f}s [{elapsed}<{remaining}]',
            )
        else:
            pbar = tqdm(desc=description, unit='frames')

        process = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1, universal_newlines=True,
        )

        while process.poll() is None:  # while the process is running
            line = process.stderr.readline()
            if not line:
                continue
            if verbose:
                print(line.strip())
            current_time = parse_progress_line(line)
            if current_time is not None:
                if total_duration:
                    pbar.n = min(current_time, total_duration)
                    pbar.refresh()
                else:
                    pbar.update(1)
                if progress_callback:
                    progress_callback(current_time)

        remaining_stderr = process.stderr.read()
        if verbose and remaining_stderr:
            print(remaining_stderr)

        return_code = process.returncode
        if total_duration:
            pbar.n = total_duration
            pbar.refresh()
        pbar.close()

        if return_code != 0:
            stderr_output = remaining_stderr or ""
            error_msg = f"FFmpeg failed with return code {return_code}"
            if stderr_output:
                error_msg += f"\nError output: {stderr_output}"
            raise subprocess.CalledProcessError(return_code, cmd, error_msg)
    except FileNotFoundError:
        if 'pbar' in locals():
            pbar.close()
        raise FileNotFoundError(
            "ffmpeg not found. Please install ffmpeg and ensure it's in your PATH."
        )
    except Exception:
        if 'pbar' in locals():
            pbar.close()
        raise
