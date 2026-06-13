# Dedupe Report

`CS-001` is a single artifact-leak finding covering multiple independently sensitive records in the same tracked FortiGate backup file. The instances are grouped because the common root cause is committing the live backup artifact despite `ansible/artifacts/` being ignored.

No duplicate high-impact command injection, MCP authorization, or ungated live mutation candidates survived discovery.
