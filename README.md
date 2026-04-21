# streamfusion-trash-mirror

Filtered mirror of [TRaSH-Guides/Guides](https://github.com/TRaSH-Guides/Guides) Custom Formats (Radarr + Sonarr) for the **Stream Fusion** streaming addon.

## What this repo contains

- **`docs/json/radarr/cf/`** — filtered subset of TRaSH Custom Formats for **movies**.
- **`docs/json/sonarr/cf/`** — filtered subset of TRaSH Custom Formats for **TV series**.
- **`templates/`** — ready-to-use scoring templates bundled with the app.
- **`metadata.json`** — machine-readable metadata consumed by the Stream Fusion sync task.
- **`.github/workflows/sync.yml`** — daily sync job.

## How the sync works

Every day at 02:00 UTC, the GitHub Actions workflow:
1. Clones `TRaSH-Guides/Guides` with sparse-checkout on `docs/json/radarr/cf/` and `docs/json/sonarr/cf/`
2. For each flavor (radarr, sonarr), copies files matching the **keep patterns** and whitelist, excluding those matching **exclude patterns** or blacklist
3. Regenerates `metadata.json` with upstream commit SHA, synced timestamp, and per-flavor counts
4. Commits and pushes if anything changed

## Templates

Templates are JSON files in `templates/` — committed directly, never overwritten by CI.

### Community templates

Want your scoring preset included as a default in all Stream Fusion instances?
Open a PR adding your template to `templates/`. Requirements:

- Filename: `<your-slug>.json` (lowercase, hyphens only)
- `is_system` must be `false` for community templates
- The file must be valid JSON and match the structure below

### Template structure

```json
{
  "slug": "my-preset",
  "name": "Human-readable name",
  "description": "What this preset optimizes for.",
  "is_system": false,
  "config": {
    "scores": {
      "<cf-slug-or-trash_id>": 500
    },
    "language_prefs": {
      "preferred_audio": ["fr", "en"],
      "preferred_subs": ["fr", "none"],
      "must_have_french_audio": false
    },
    "constraints": {
      "min_score": null,
      "max_size_gb": null,
      "ban_below": -1000
    },
    "weights": {
      "rtn_base": 0.0,
      "cf_score": 1.0,
      "language_bonus": 0.3
    }
  }
}
```

Keys in `scores` can be either a **`trash_id` UUID** or a **CF filename stem** (e.g. `"french-web-tier-01"`). The Stream Fusion sync task resolves stems to UUIDs at upsert time.

## Attribution

All Custom Format JSON files are copyright of the [TRaSH-Guides](https://github.com/TRaSH-Guides/Guides) project and redistributed under their terms.
