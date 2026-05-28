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

## Credentials

Use 1Password runtime injection. Do not write tokens to disk.

Expected environment variable:

```bash
export FORTIOS_ACCESS_TOKEN="op://d3HLPRV/fortigate-100f/access_token"
```

If the item does not have `access_token`, create one in FortiGate for API automation and store it in the `fortigate-100f` item.

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

5. Apply only after review:

```bash
cd ansible
export FORTIOS_ACCESS_TOKEN="op://d3HLPRV/fortigate-100f/access_token"
export CONFIRM_FORTIGATE_APPLY=yes
op run -- ansible-playbook playbooks/fortigate/apply-vlan-interfaces.yml --diff
```

## Safety Notes

- The apply playbook refuses to run while `fortigate_parent_interface` is `__CONFIRM_PARENT_INTERFACE__`.
- The apply playbook refuses to run unless `CONFIRM_FORTIGATE_APPLY=yes`.
- FortiGate candidate VLAN interfaces currently include VLANs `10,20,30,40,50,60,99`; verify the C9300 trunk to FortiGate allows the required VLANs before expecting end-to-end reachability.
