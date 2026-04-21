"""
Sync script for streamfusion-trash-mirror.

- Copies filtered CF JSON files from upstream/docs/json/{radarr,sonarr}/cf
  to docs/json/{radarr,sonarr}/cf/
- Regenerates metadata.json (templates/ is never touched by this script)
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

UPSTREAM_CF_DIRS = {
    "radarr": ROOT / "upstream" / "docs" / "json" / "radarr" / "cf",
    "sonarr": ROOT / "upstream" / "docs" / "json" / "sonarr" / "cf",
}
DEST_CF_DIRS = {
    "radarr": ROOT / "docs" / "json" / "radarr" / "cf",
    "sonarr": ROOT / "docs" / "json" / "sonarr" / "cf",
}
DEST_TEMPLATES = ROOT / "templates"
METADATA_PATH = ROOT / "metadata.json"
UPSTREAM_SHA = os.environ.get("UPSTREAM_SHA", "")

# =============================================================================
# FILTRAGE
#
# Algorithme (appliqué au stem lowercase du fichier, sans .json) :
#   1. Si stem ∈ BLACKLIST_EXTRA                              → False
#   2. Si un EXCLUDE_PATTERN matche ET stem ∉ WHITELIST_EXTRA → False
#   3. Si stem ∈ WHITELIST_EXTRA                              → True
#   4. Si un KEEP_PATTERN matche                              → True
#   5. Sinon                                                  → False
#
# Patterns = substrings case-insensitive.
# =============================================================================

KEEP_PATTERNS = [
    # Français
    "french-",

    # Anime (inclus : tiers BD/WEB + anime-raws, anime-dual-audio, anime-lq-groups)
    "anime-",

    # Résolutions
    "720p", "1080p", "2160p",

    # Codecs vidéo
    "x264", "x265", "x266",
    "av1", "vp9", "vc-1", "mpeg2",
    "10bit",

    # HDR / SDR
    "hdr", "dv-", "sdr",
    "generated-dynamic-hdr",

    # Audio codecs
    "aac", "flac", "mp3", "opus", "pcm",
    "dd", "ddplus", "dts", "truehd", "atmos-",

    # Audio channels
    "-mono", "-stereo", "-sound", "-surround",

    # Tiers qualité & boosters
    "tier-",
    "br-disk",
    "4k-remaster",
    "-boost",
    "remux-tier",

    # Features
    "repack", "proper", "remaster",

    # Filtres langue utiles pour public FR
    "language-not-english",
    "language-not-french",
    "language-original-plus-french",
]

EXCLUDE_PATTERNS = [
    # Allemand (exception gérée par WHITELIST_EXTRA)
    "german-",
    "language-german",
    "language-not-german",

    # Autres langues non ciblées
    "dutch-",
    "italian-",
    "spanish-",
    "portuguese-",
    "russian-",
    "polish-",
    "nordic",

    # Accessibilité hors scope
    "with-ad", "with-asl", "with-basl", "with-bsl",

    # Niches visuelles hors scope
    "3d",
    "black-and-white",
    "line-mic",
    "sing-along",
    "open-matte",
    "vinegar-syndrome",

    # Boosters régionaux DE
    "german-1080p-booster",
    "german-2160p-booster",
]

# Whitelist : CFs utiles sans pattern évident OU échappant à un EXCLUDE_PATTERN.
# Matching EXACT sur le stem lowercase.
WHITELIST_EXTRA = {
    # Streaming majeurs globaux (contenu FR probable)
    "amzn", "atv", "atvp", "nf", "dsnp", "max", "hbo", "hulu",
    "hmax", "pcok", "pmtp", "pathe",

    # Multi & flags techniques
    "multi",
    "hybrid",
    "internal", "p2p-internal",
    "obfuscated",
    "retags",
    "upscaled",
    "no-rlsgroup",

    # Groupes sélectionnés
    "scene", "flux", "mainframe",
    "bad-dual-groups",

    # Features qualité
    "extras",
    "special-edition", "theatrical-cut",
    "imax", "imax-enhanced",
    "criterion-collection", "masters-of-cinema",
    "season-pack", "single-episode", "multi-episode",
    "uncensored", "freeleech",
    "hfr",

    # Anti-LQ généraux
    "lq", "lq-release-title",

    # Pénalités DE (exception au pattern EXCLUDE "german-")
    "german-lq", "german-lq-release-title",

    # Variantes x265 particulières
    "x265-hd", "x265-no-hdrdv",
    "sdr-no-webdl",

    # Anime flags additionnels
    "fansub", "fastsub", "dubs-only",
    "v0", "v1", "v2", "v3", "v4",
}

# Blacklist : exclusions chirurgicales appliquées en tout premier.
BLACKLIST_EXTRA = {
    # CF orphelin au nom numérique
    "126811",

    # Filtres langue non pertinents
    "wrong-language",
    "language-not-original",

    # Groupes nichés sans valeur pour public FR
    "thefarm", "hallowed", "bcore", "bhdstudio", "framestor", "crit",

    # Groupes NL
    "dutch-groups",

    # Streaming régionaux non-FR
    "4od", "abema", "all4", "aubc",
    "bglobal", "bilibili",
    "cbc", "cc", "cr", "crav",
    "dcu", "dscp",
    "fod", "funi",
    "hidive", "htsr",
    "ip", "it", "itvx", "ma",
    "my5", "nlz", "now",
    "ovid", "play",
    "qibi", "red", "roku",
    "sho", "sic", "stan", "strp", "syfy",
    "tver", "tving",
    "u-next",
    "vdl", "viu", "vrv",
}


def _matches_any(name: str, patterns: list[str]) -> bool:
    name_lc = name.lower()
    return any(p.lower() in name_lc for p in patterns)


def should_keep(filename: str) -> bool:
    stem = (filename[:-5] if filename.endswith(".json") else filename).lower()

    if stem in BLACKLIST_EXTRA:
        return False

    if _matches_any(stem, EXCLUDE_PATTERNS) and stem not in WHITELIST_EXTRA:
        return False

    if stem in WHITELIST_EXTRA:
        return True

    if _matches_any(stem, KEEP_PATTERNS):
        return True

    return False


def sync_custom_formats() -> dict[str, int]:
    counts: dict[str, int] = {}

    for flavor, src_dir in UPSTREAM_CF_DIRS.items():
        dst_dir = DEST_CF_DIRS[flavor]

        if dst_dir.exists():
            for f in dst_dir.glob("*.json"):
                f.unlink()
        dst_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        if not src_dir.exists():
            print(f"WARN: upstream CF dir not found for {flavor}: {src_dir}")
            counts[flavor] = 0
            continue

        for src in sorted(src_dir.glob("*.json")):
            if not should_keep(src.name):
                continue
            try:
                data = json.loads(src.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"SKIP (invalid JSON) [{flavor}]: {src.name}: {e}")
                continue
            if "trash_id" not in data or "name" not in data:
                print(f"SKIP (missing trash_id/name) [{flavor}]: {src.name}")
                continue
            shutil.copy2(src, dst_dir / src.name)
            count += 1

        print(f"[{flavor}] Synced {count} custom formats")
        counts[flavor] = count

    return counts


def write_metadata(cf_counts: dict[str, int]) -> None:
    template_count = len(list(DEST_TEMPLATES.glob("*.json"))) if DEST_TEMPLATES.exists() else 0
    meta = {
        "version": UPSTREAM_SHA or "unknown",
        "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "upstream_sha": UPSTREAM_SHA,
        "cf_count": sum(cf_counts.values()),
        "cf_count_radarr": cf_counts.get("radarr", 0),
        "cf_count_sonarr": cf_counts.get("sonarr", 0),
        "template_count": template_count,
        "keep_patterns": KEEP_PATTERNS,
        "exclude_patterns": EXCLUDE_PATTERNS,
        "whitelist_extra": sorted(WHITELIST_EXTRA),
        "blacklist_extra": sorted(BLACKLIST_EXTRA),
    }
    METADATA_PATH.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote metadata: cf_count={meta['cf_count']} "
        f"(radarr={meta['cf_count_radarr']}, sonarr={meta['cf_count_sonarr']}), "
        f"templates={template_count}"
    )


def main() -> None:
    cf_counts = sync_custom_formats()
    write_metadata(cf_counts)


if __name__ == "__main__":
    main()
