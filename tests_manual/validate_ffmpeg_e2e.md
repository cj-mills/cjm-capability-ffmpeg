# Tombstone — `validate_ffmpeg_e2e.py` (RETIRED 2026-06-18, stage 9)

**Origin:** `cjm-media-plugin-ffmpeg/tests_manual/validate_ffmpeg_e2e.py` (2026-05-31, Phase-5 era).
**Retired because:** per-tool e2e validator superseded by the cores' standing harness; the cohort is retired, not patched.

**What it validated:** the plugin still works after the 5 ffmpeg helpers were lifted out of the retired `cjm-ffmpeg-utils` into this plugin's own `utils/` sub-package (availability / codec / probe / progress / segments), plus the meta.py manifest overhaul (T24 description + CR-7 resource reframe).

**Coverage status:** SUPERSEDED — ffmpeg's `media_processing` ops (convert / segment / extract_audio / get_info) are exercised through `cjm-transcription-core`'s task-channel call-sites, validated byte-stable on the SN-I both-transcriber corpus.

**Reimplementation target:** none required (cores are the standing harness).
