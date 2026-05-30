# FortiGate Ansible Runbook

This repo uses the `fortinet.fortios` Ansible collection for FortiGate automation.

Official docs checked:

- `fortinet.fortios` collection index: https://docs.ansible.com/projects/ansible/latest/collections/fortinet/fortios/index.html
- `fortios_configuration_fact`: https://docs.ansible.com/projects/ansible/latest/collections/fortinet/fortios/fortios_configuration_fact_module.html
- `fortios_system_interface`: https://docs.ansible.com/projects/ansible/latest/collections/fortinet/fortios/fortios_system_interface_module.html

## Install Collection

```bash
cd ansible
ansible-galaxy collection install -r collections/requirements.yml
```

Run Ansible from WSL, Linux, or another supported Ansible control host. The
Windows Python Ansible CLI in this workstation currently fails during CLI
startup with `OSError: [WinError 87] The parameter is incorrect`.

On this workstation, use `configs/fortigate-api-apply-vlans.py` as the gated
fallback. It reads the same `ansible/group_vars/fortigates.yml` intent and uses
the FortiGate REST API token from 1Password.

FortiGate API endpoint verified from this workstation:

```text
https://10.99.99.2:7443
```

## Credentials

Use 1Password runtime injection. Do not write tokens to disk.

Expected environment variable:

```bash
export FORTIOS_ACCESS_TOKEN="op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential"
```

The originally documented `fortigate-100f` item was not present during the
2026-05-28 verification attempt. The discovered token item was
`FORTIOS_ACCESS_TOKEN` with concealed field `credential`.

If you prefer the stable item name `fortigate-100f`, create it and store the
API token in an `access_token` field, then update this runbook and
`ansible/group_vars/fortigates.yml` accordingly.

## Read-Only Discovery (Interfaces + Policies)

After `op signin` or with `OP_SERVICE_ACCOUNT_TOKEN` set:

```bash
bash configs/fortigate-discover-op-run.sh
```

Artifacts:

- `ansible/artifacts/fortigate-verification.json` (interface intent comparison)
- `ansible/artifacts/fortigate-discovery.json` (interfaces, zones, homelab-related policies)

## Safe Workflow

1. Discover current interfaces:

```bash
cd ansible
op run -- ansible-playbook playbooks/fortigate/discover.yml
```

2. Render the candidate VLAN interface plan:

```bash
cd ansible
ansible-playbook playbooks/fortigate/render-vlan-plan.yml
```

3. Review `ansible/artifacts/fortigate-vlan-interface-plan.md`.

4. Replace `fortigate_parent_interface` in `ansible/group_vars/fortigates.yml` with the discovered trunk parent interface.

   Current verified parent interface: `x2`.

5. Apply only after review:

```bash
cd ansible
export FORTIOS_ACCESS_TOKEN="op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential"
export CONFIRM_FORTIGATE_APPLY=yes
export CONFIRM_FORTIGATE_TRUNK_REVIEW=yes
op run -- ansible-playbook playbooks/fortigate/apply-vlan-interfaces.yml --diff
```

Fallback from this Windows workstation:

```powershell
$env:FORTIGATE_HOST='https://10.99.99.2:7443'
$env:FORTIOS_ACCESS_TOKEN='op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential'
$env:CONFIRM_FORTIGATE_APPLY='yes'
$env:CONFIRM_FORTIGATE_TRUNK_REVIEW='yes'
op run -- python configs\fortigate-api-apply-vlans.py
```

## Safety Notes

- The apply playbook refuses to run while `fortigate_parent_interface` is `__CONFIRM_PARENT_INTERFACE__`.
- The apply playbook refuses to run unless `CONFIRM_FORTIGATE_APPLY=yes`.
- The apply playbook also refuses to run unless `CONFIRM_FORTIGATE_TRUNK_REVIEW=yes`.
- FortiGate candidate VLAN interfaces currently include only VLANs `30,40,50,60`; verify the C9300 trunk to FortiGate carries `10,11,30,40,50,60,100` before expecting end-to-end reachability.
- The 2026-05-28 retry verified the FortiGate API at `https://10.99.99.2:7443`.
- Current adopted live model:
  - VLAN 10 is tracked as existing interface `hlvl` on parent `x2` with `10.10.10.2/24`.
  - VLAN 99 stays on existing `mgt` hard-switch with `10.99.99.2/24`.
  - VLAN 20 remains on the C9300/storage side and is not routed to the FortiGate.
  - VLANs 30, 40, 50, and 60 use short FortiOS-safe interface names: `vsvc`, `vapps`, `vlab`, and `vdmz`.
