# Attack Path Analysis: CS-001

## Attack Path

1. Attacker obtains repository read access through a fork, shared workspace, backup, or compromised developer account.
2. Attacker reads `ansible/artifacts/fortigate-config-backup.conf`.
3. The file discloses a full FortiGate backup containing encrypted API key/password/private-key/PSK material plus detailed firewall/VPN configuration.
4. Attacker can attempt offline recovery, leverage exposed certificates/keys if passphrases are weak or separately leaked, or use the configuration to target VPN/firewall management paths.

## Severity

High. The artifact contains encrypted credential material and private keys from a live firewall backup. Encryption reduces immediate exploitability but does not make the material safe to commit. The appropriate response is to remove the artifact from git history/current tree and rotate affected API keys, certificate/private key material, VPN PSKs, and any backup-contained secrets according to FortiGate operational constraints.
