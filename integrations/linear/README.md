# Linear backlog sync — Cloudflare Control Plane (NCD-28)

This directory holds the backlog backfill tooling for the **cf-controller** / **Cloudflare Control Plane** project.

The canonical home for these files is `d3hl/cf-controller`. Cloud Agents without write access to that repo can run the sync from here, then port the same files into cf-controller.

## Quick start

```bash
export LINEAR_API_KEY="lin_api_..."
python3 integrations/linear/sync-features.py \
  --feature-list integrations/linear/cf-controller-feature_list.json \
  --write-mapping
```

Dry run:

```bash
python3 integrations/linear/sync-features.py \
  --feature-list integrations/linear/cf-controller-feature_list.json \
  --dry-run
```

## What gets synced

Eight CF-01 harness features (`CF-000` … `CF-007`) are created in the Linear project **Cloudflare Control Plane** with workflow state **Backlog**.

See `cf-controller-workflow.md` for the harness ↔ Linear mapping.

## Port back to cf-controller

When you have push access to `d3hl/cf-controller`, copy:

- `cf-controller-feature_list.json` → `feature_list.json`
- `sync-features.py` → `scripts/linear-sync-features.py`
- `cf-controller-workflow.md` → `docs/linear-workflow.md`
