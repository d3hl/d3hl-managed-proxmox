# Linear workflow — CF-01 / Cloudflare Control Plane

`feature_list.json` is the harness source of truth. Linear is the execution and prioritization layer.

## Project

- Team key: `NCD`
- Project: **Cloudflare Control Plane**
- Sync task: `NCD-28` — backfill all CF-01 harness features as Backlog issues

## Status mapping

| Harness status | Linear state on initial sync |
|---|---|
| `not_started` | Backlog |
| `in_progress` | Backlog |
| `blocked` | Backlog |
| `passing` | Backlog |

After backfill, move completed work to **Done** manually or with a follow-up sync script.

## Feature mapping

| Harness | Title | Initial Linear state |
|---|---|---|
| CF-000 | Create repo harness and static baseline | Backlog |
| CF-001 | Terraform Cloudflare DNS baseline | Backlog |
| CF-002 | Terraform Cloudflare zone security settings | Backlog |
| CF-003 | Document 1Password-backed Terraform runner contract | Backlog |
| CF-004 | cloudflared tunnel connector deployment | Backlog |
| CF-005 | Mesh controller service scaffold | Backlog |
| CF-006 | Add GitHub Actions static checks | Backlog |
| CF-007 | Define end-to-end validation runbook | Backlog |

Populate the `linear_issue` column in `feature_list.json` after sync.

## Sync command

```bash
export LINEAR_API_KEY="lin_api_..."   # personal API key with issue create permission
python3 scripts/linear-sync-features.py --write-mapping
```

Dry run:

```bash
python3 scripts/linear-sync-features.py --dry-run
```

## Idempotency rules

- Issues are matched by `[CF-xxx]` marker in title or description.
- Existing mappings in `feature_list.json` are not recreated.
- New features should always include a stable harness `id`.

## Cursor / MCP note

Linear MCP in Cursor requires desktop authentication. If MCP is unavailable, use `scripts/linear-sync-features.py` with `LINEAR_API_KEY` instead. The harness remains authoritative when Linear is unreachable.
