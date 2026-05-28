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
op run -- ansible-playbook playbooks/fortigate/apply-vlan-interfaces.yml --diff
```

## Safety Notes

- The apply playbook refuses to run while `fortigate_parent_interface` is `__CONFIRM_PARENT_INTERFACE__`.
- The apply playbook refuses to run unless `CONFIRM_FORTIGATE_APPLY=yes`.
- FortiGate candidate VLAN interfaces currently include VLANs `10,20,30,40,50,60,99`; verify the C9300 trunk to FortiGate allows the required VLANs before expecting end-to-end reachability.
- The 2026-05-28 retry verified the FortiGate API at `https://10.99.99.2:7443`.
- Do not apply the current VLAN list as-is without reconciling live state:
  - VLAN 10 already exists as `hlvl` on parent `x2` with `10.10.10.2/24`.
  - VLAN 99 IP `10.99.99.2/24` is already used by `mgt` hard-switch.
  - VLANs 20, 30, 40, 50, and 60 are missing.
