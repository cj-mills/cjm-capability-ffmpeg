"""FFmpeg plugin end-to-end validation (Phase 5 — cjm-ffmpeg-utils retirement).

Proves the plugin works after the 5 ffmpeg helper functions were LIFTED out of
the retired `cjm-ffmpeg-utils` library into this plugin's own `utils/` sub-package
(availability / codec / probe / progress / segments), and after the meta.py
manifest overhaul (T24 description + CR-7 resource reframe).

Run from the ffmpeg repo root after:
  1. `cjm-ctl --cjm-config cjm.yaml setup-runtime`
  2. `cjm-ctl --cjm-config cjm.yaml install-all --plugins plugins_test.yaml --force`
     (--force REQUIRED — rebuilds the worker env so cjm-ffmpeg-utils is GONE)
  3. A real audio file at test_files/sample_audio.mp3

Then:
  conda run -n cjm-media-plugin-ffmpeg --no-capture-output \\
    python tests_manual/validate_ffmpeg_e2e.py

This script:
  - Verifies the v2.0 manifest carries (a) a non-empty `description`, (b) the
    media/MediaProcessingPlugin taxonomy, and (c) requires_gpu=False with NO
    quantitative resource fields (the CR-7 reframe / V12 gate).
  - Loads the plugin in a real worker subprocess (whose env no longer contains
    cjm-ffmpeg-utils) and exercises get_info / extract_segment / convert.
  - Confirms the Layer C content+config cache: a second identical convert returns
    the same path WITHOUT inserting a new job row (cache hit).
"""
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
)
log = logging.getLogger("ffmpeg-e2e")

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_AUDIO = REPO_ROOT / "test_files" / "sample_audio.mp3"
MANIFESTS_DIR = REPO_ROOT / ".cjm" / "manifests"

PLUGIN_NAME = "cjm-media-plugin-ffmpeg"


def check_prereqs() -> None:
    assert TEST_AUDIO.exists(), f"Missing test audio: {TEST_AUDIO}"
    assert MANIFESTS_DIR.exists(), (
        f"Missing manifests dir: {MANIFESTS_DIR} — run cjm-ctl setup-runtime + install-all --force first"
    )
    assert (MANIFESTS_DIR / f"{PLUGIN_NAME}.json").exists(), f"Missing manifest: {PLUGIN_NAME}.json"
    log.info("Prereqs OK: test audio + ffmpeg manifest present")


def assert_manifest_shape() -> None:
    manifest = json.loads((MANIFESTS_DIR / f"{PLUGIN_NAME}.json").read_text())
    assert manifest["format_version"] == "2.0", manifest["format_version"]
    code = manifest["code"]

    desc = code.get("description") or manifest.get("description") or ""
    assert desc.strip(), "manifest description is empty (T24 regression)"
    log.info(f"Manifest T24 description: {desc!r}")

    tax = code["taxonomy"]
    assert tax["domain"] == "media" and tax["role"] == "MediaProcessingPlugin", tax
    assert code["resources"]["requires_gpu"] is False, code["resources"]
    for stale in ("min_gpu_vram_mb", "recommended_gpu_vram_mb", "min_system_ram_mb"):
        assert stale not in code["resources"], f"stale resource field present: {stale}"
    log.info(f"Manifest CR-1/Phase-5a: taxonomy={tax}, resources={code['resources']}")


def _convert_row_count(db_path: str) -> int:
    if not db_path or not Path(db_path).exists():
        return 0
    con = sqlite3.connect(db_path)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        total = 0
        for t in tables:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})").fetchall()]
            if "action" in cols:
                total += con.execute(
                    f"SELECT COUNT(*) FROM {t} WHERE action='convert'").fetchone()[0]
        return total
    finally:
        con.close()


def run_e2e() -> None:
    from cjm_plugin_system.core.manager import PluginManager
    from cjm_plugin_system.core.config import get_config

    cfg = get_config()
    log.info(f"data_dir={cfg.data_dir}, models_dir={cfg.models_dir}")

    pm = PluginManager(search_paths=[MANIFESTS_DIR])
    pm.discover_manifests()
    log.info(f"Discovered: {[m.name for m in pm.discovered]}")

    ffmpeg_meta = next(m for m in pm.discovered if m.name == PLUGIN_NAME)
    db_path = ffmpeg_meta.manifest.get("db_path")
    ok = pm.load_plugin(ffmpeg_meta, config={})
    assert ok, f"Failed to load {PLUGIN_NAME}"
    log.info(f"Loaded {PLUGIN_NAME} in a worker subprocess; db_path={db_path}")

    try:
        # 1) get_info -> probe (utils.probe is exercised indirectly; ffprobe directly here)
        info = pm.execute_plugin(PLUGIN_NAME, action="get_info", file_path=str(TEST_AUDIO))
        duration = info["duration"] if isinstance(info, dict) else getattr(info, "duration", 0)
        assert duration and duration > 0, f"get_info returned no duration: {info!r}"
        log.info(f"get_info OK: duration={duration:.1f}s, format={info.get('format')}")

        # 2) extract_segment -> utils.segments.extract_audio_segment (stream copy, tiny output)
        seg = pm.execute_plugin(
            PLUGIN_NAME, action="extract_segment",
            input_path=str(TEST_AUDIO), start=0.0, end=10.0,
        )
        seg_path = seg["output_path"]
        assert Path(seg_path).exists(), f"extract_segment output missing: {seg_path}"
        assert "extract_segment" in seg_path, f"output not under cache layout: {seg_path}"
        log.info(f"extract_segment OK: {seg_path}")

        # 3) convert -> utils.codec.get_audio_codec + utils.probe.get_media_duration
        #    + utils.progress.run_ffmpeg_with_progress (the full lifted chain)
        n_before = _convert_row_count(db_path)
        out1 = pm.execute_plugin(
            PLUGIN_NAME, action="convert",
            input_path=seg_path, output_format="wav",
        )["output_path"]
        assert Path(out1).exists(), f"convert output missing: {out1}"
        assert "convert" in out1, f"convert output not under cache layout: {out1}"
        n_after = _convert_row_count(db_path)
        assert n_after == n_before + 1, f"expected 1 new convert row, got {n_after - n_before}"
        log.info(f"convert OK: {out1} (job rows {n_before} -> {n_after})")

        # 4) convert again -> Layer C cache HIT: same path, NO new job row
        out2 = pm.execute_plugin(
            PLUGIN_NAME, action="convert",
            input_path=seg_path, output_format="wav",
        )["output_path"]
        assert out2 == out1, f"cache miss: {out2} != {out1}"
        n_cached = _convert_row_count(db_path)
        assert n_cached == n_after, f"cache hit should add no rows: {n_cached} != {n_after}"
        log.info(f"convert cache HIT OK: same path, job rows still {n_cached}")
    finally:
        pm.unload_plugin(PLUGIN_NAME)
        log.info("Unloaded plugin.")


def main() -> int:
    check_prereqs()
    assert_manifest_shape()
    run_e2e()
    log.info("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
