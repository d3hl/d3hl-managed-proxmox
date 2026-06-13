# Validation Report: CS-001

## Verdict

Reportable.

## Evidence

- `ansible/artifacts/fortigate-config-backup.conf:461` contains `set api-key ENC ...`.
- `ansible/artifacts/fortigate-config-backup.conf:9094`, `9155`, `9216`, `9276`, and `9367` contain encrypted password material.
- `ansible/artifacts/fortigate-config-backup.conf:9096`, `9157`, `9218`, `9278`, and `9369` start encrypted private-key blocks.
- `ansible/artifacts/fortigate-config-backup.conf:10226` enables `save-password`; `10227` contains encrypted PSK material.
- `git check-ignore -v ansible/artifacts/fortigate-config-backup.conf` reports the path is ignored by `.gitignore`, but `git ls-files ansible/artifacts/fortigate-config-backup.conf` lists it, proving the ignored live backup remains tracked.

## Notes

FortiGate `ENC` fields and encrypted private keys are not plaintext, but encrypted device backups are still sensitive credential-bearing artifacts. Committing them materially increases blast radius for anyone with repository access and makes rotation/revocation a necessary response.
