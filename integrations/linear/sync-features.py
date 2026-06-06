#!/usr/bin/env python3
"""Sync cf-controller feature_list.json issues into Linear as Backlog items."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LINEAR_API_URL = "https://api.linear.app/graphql"
ROOT = Path(__file__).resolve().parents[1]
FEATURE_LIST = ROOT / "feature_list.json"


class LinearError(RuntimeError):
    pass


def graphql(api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    request = urllib.request.Request(
        LINEAR_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LinearError(f"Linear HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LinearError(f"Linear request failed: {exc}") from exc

    if body.get("errors"):
        raise LinearError(json.dumps(body["errors"], indent=2))
    return body["data"]


def load_features(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    features = [feature for feature in data.get("features", []) if feature.get("id")]
    if not features:
        raise LinearError(f"No features with ids found in {path}")
    return data


def find_team(api_key: str, team_key: str) -> dict[str, Any]:
    data = graphql(
        api_key,
        """
        query Teams {
          teams {
            nodes {
              id
              key
              name
            }
          }
        }
        """,
    )
    for team in data["teams"]["nodes"]:
        if team["key"].upper() == team_key.upper():
            return team
    available = ", ".join(team["key"] for team in data["teams"]["nodes"])
    raise LinearError(f"Team key {team_key!r} not found. Available: {available}")


def find_project(api_key: str, project_name: str) -> dict[str, Any]:
    data = graphql(
        api_key,
        """
        query Projects {
          projects {
            nodes {
              id
              name
            }
          }
        }
        """,
    )
    for project in data["projects"]["nodes"]:
        if project["name"].strip().lower() == project_name.strip().lower():
            return project
    available = ", ".join(project["name"] for project in data["projects"]["nodes"])
    raise LinearError(f"Project {project_name!r} not found. Available: {available}")


def find_backlog_state(api_key: str, team_id: str) -> dict[str, Any]:
    data = graphql(
        api_key,
        """
        query TeamStates($teamId: String!) {
          team(id: $teamId) {
            states {
              nodes {
                id
                name
                type
              }
            }
          }
        }
        """,
        {"teamId": team_id},
    )
    states = data["team"]["states"]["nodes"]
    for state in states:
        if state["type"] == "backlog":
            return state
    for state in states:
        if state["name"].strip().lower() == "backlog":
            return state
    raise LinearError(f"No backlog workflow state found for team {team_id}")


def list_project_issues(api_key: str, project_id: str) -> list[dict[str, Any]]:
    data = graphql(
        api_key,
        """
        query ProjectIssues($projectId: String!) {
          project(id: $projectId) {
            issues {
              nodes {
                id
                identifier
                title
                description
              }
            }
          }
        }
        """,
        {"projectId": project_id},
    )
    return data["project"]["issues"]["nodes"]


def feature_marker(feature_id: str) -> str:
    return f"[{feature_id}]"


def issue_matches_feature(issue: dict[str, Any], feature: dict[str, Any]) -> bool:
    marker = feature_marker(feature["id"])
    title = issue.get("title") or ""
    description = issue.get("description") or ""
    return title.startswith(marker) or marker in description


def build_description(feature: dict[str, Any]) -> str:
    lines = [
        feature_marker(feature["id"]),
        "",
        feature.get("description", ""),
        "",
        f"Harness status: `{feature.get('status', 'unknown')}`",
        f"Area: `{feature.get('area', 'unknown')}`",
        f"Priority: `{feature.get('priority', 'unknown')}`",
    ]
    dependencies = feature.get("dependencies") or []
    if dependencies:
        lines.extend(["", "Dependencies:", ", ".join(f"`{item}`" for item in dependencies)])
    verification = feature.get("verification") or []
    if verification:
        lines.append("")
        lines.append("Verification:")
        lines.extend(f"- {item}" for item in verification)
    notes = feature.get("notes")
    if notes:
        lines.extend(["", f"Notes: {notes}"])
    return "\n".join(lines)


def create_issue(
    api_key: str,
    *,
    team_id: str,
    project_id: str,
    state_id: str,
    feature: dict[str, Any],
) -> dict[str, Any]:
    title = f"{feature_marker(feature['id'])} {feature['title']}"
    data = graphql(
        api_key,
        """
        mutation CreateIssue($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue {
              id
              identifier
              title
              url
            }
          }
        }
        """,
        {
            "input": {
                "teamId": team_id,
                "projectId": project_id,
                "stateId": state_id,
                "title": title,
                "description": build_description(feature),
                "priority": max(0, 5 - int(feature.get("priority", 3))),
            }
        },
    )
    result = data["issueCreate"]
    if not result["success"]:
        raise LinearError(f"Failed to create issue for {feature['id']}")
    return result["issue"]


def update_feature_list(path: Path, mapping: dict[str, str]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for feature in data.get("features", []):
        feature_id = feature.get("id")
        if feature_id in mapping and feature.get("linear_issue") != mapping[feature_id]:
            feature["linear_issue"] = mapping[feature_id]
            changed = True
    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feature-list",
        type=Path,
        default=FEATURE_LIST,
        help="Path to feature_list.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without creating Linear issues",
    )
    parser.add_argument(
        "--write-mapping",
        action="store_true",
        help="Write created Linear identifiers back into feature_list.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("LINEAR_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        print("LINEAR_API_KEY is required unless --dry-run is set.", file=sys.stderr)
        return 2

    data = load_features(args.feature_list)
    linear_meta = data.get("linear", {})
    team_key = linear_meta.get("team_key", "NCD")
    project_name = linear_meta.get("project_name", "Cloudflare Control Plane")

    if args.dry_run:
        print(f"Would sync {len(data['features'])} features to Linear project {project_name!r} as Backlog")
        for feature in data["features"]:
            print(f"- {feature['id']}: {feature['title']}")
        return 0

    team = find_team(api_key, team_key)
    project = find_project(api_key, project_name)
    backlog_state = find_backlog_state(api_key, team["id"])
    existing_issues = list_project_issues(api_key, project["id"])

    created: dict[str, str] = {}
    skipped: dict[str, str] = {}

    for feature in data["features"]:
        feature_id = feature["id"]
        if feature.get("linear_issue"):
            skipped[feature_id] = feature["linear_issue"]
            print(f"skip {feature_id}: already mapped to {feature['linear_issue']}")
            continue

        matched = next((issue for issue in existing_issues if issue_matches_feature(issue, feature)), None)
        if matched:
            skipped[feature_id] = matched["identifier"]
            print(f"skip {feature_id}: found existing {matched['identifier']}")
            continue

        issue = create_issue(
            api_key,
            team_id=team["id"],
            project_id=project["id"],
            state_id=backlog_state["id"],
            feature=feature,
        )
        created[feature_id] = issue["identifier"]
        print(f"create {feature_id}: {issue['identifier']} {issue['url']}")

    if args.write_mapping and (created or skipped):
        update_feature_list(args.feature_list, {**skipped, **created})
        print(f"updated mapping in {args.feature_list}")

    print(
        json.dumps(
            {
                "team": team["key"],
                "project": project["name"],
                "backlog_state": backlog_state["name"],
                "created": created,
                "skipped": skipped,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
