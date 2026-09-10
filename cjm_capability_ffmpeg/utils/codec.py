"""Map audio container formats to the ffmpeg codec used to encode them, and
audio codecs back to the audio-only container that holds them under stream copy."""

from typing import Optional


def get_audio_codec(audio_format: str  # The desired audio format (e.g. 'mp3', 'wav')
                   ) -> str:  # The ffmpeg audio codec name ('copy' if unknown)
    """Map an audio container format to the appropriate ffmpeg codec."""
    codec_map = {
        'mp3': 'libmp3lame',
        'wav': 'pcm_s16le',
        'flac': 'flac',
        'aac': 'aac',
        'ogg': 'libvorbis',
        'm4a': 'aac',
    }
    return codec_map.get(audio_format.lower(), 'copy')


# Audio codec (as ffprobe names it) -> the audio-only container extension that
# can hold that stream under `-acodec copy` (no re-encode). Shared by
# `extract_audio` (whole-file) and `segment_audio` (per-boundary cuts): both
# must emit AUDIO-ONLY files even when the input is a video container, so the
# cut never drags the video stream through a software re-encode (finding
# 63861c91: ~10 min per 4-minute segment on a VP9 source).
AUDIO_ONLY_EXTENSIONS = {
    'aac': 'm4a', 'mp3': 'mp3', 'vorbis': 'ogg', 'opus': 'ogg',
    'flac': 'flac', 'pcm_s16le': 'wav', 'pcm_s24le': 'wav',
}

# Container extensions that are audio-only by construction: an input carrying
# one of these keeps its own extension on a stream-copied cut.
AUDIO_ONLY_SUFFIXES = {'aac', 'flac', 'm4a', 'mp3', 'ogg', 'opus', 'wav', 'wma'}


def get_audio_extension(codec: Optional[str]  # An audio codec name as reported by ffprobe
                       ) -> Optional[str]:  # The audio-only container extension, or None if unmapped
    """Map a detected audio codec to the audio-only container that stream-copies it."""
    if not codec:
        return None
    return AUDIO_ONLY_EXTENSIONS.get(codec.lower())
