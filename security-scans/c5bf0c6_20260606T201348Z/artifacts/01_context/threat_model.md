# Threat Model: d3hl-managed-proxmox

## Overview

This repository contains privileged homelab network automation for Proxmox SDN, FortiGate 100F, Cisco C9300, and MCP-based Proxmox access. Security impact centers on live device mutation, secret handling, MCP tool boundaries, and checked-in network state.

## Threat Model, Trust Boundaries, and Assumptions

Assets include device credentials and tokens, 1Password references, network intent, firewall policy, SDN state, and live artifacts. Trust boundaries include the local operator shell, secret-manager injection, remote device APIs and SSH, MCP tool calls, and tracked artifacts.

Realistic attackers are malicious repo contributors, compromised local environments, unsafe MCP clients, or accidental credential commits. The repo is not a public web service; unauthenticated internet-user attacks are lower likelihood unless automation is exposed elsewhere.

## Attack Surface, Mitigations, and Attacker Stories

Attack surfaces include `configs/` automation, shell and PowerShell wrappers, Ansible FortiGate intent, MCP code, `data/` JSON, docs, and tracked artifacts. Existing mitigations include `CONFIRM_*` gates, `op://` secret references, read-before-write runbooks, validation before persistent save, and baseline `init.sh` checks.

Important attacker stories include command injection through local/env/script inputs, unsafe live device mutation without confirmation gates, MCP tool calls that can trigger unauthorized Proxmox operations, and credential leakage into tracked artifacts.

## Severity Calibration

Critical: committed live credentials, arbitrary command execution, or ungated persistent destructive device changes.

High: command injection, unsafe MCP mutation, missing live-write gates, or secret leakage.

Medium: broad tokens, disabled TLS verification with constrained reachability, topology disclosure, or incomplete safety validation.

Low: non-secret docs disclosure or developer-only robustness issues.
