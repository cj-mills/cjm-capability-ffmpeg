"""Map audio container formats to the ffmpeg codec used to encode them."""


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
