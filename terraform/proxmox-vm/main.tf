# Clone-based VM on the homelab Proxmox cluster, attached to VM_SERVICES (VLAN 30).
# Runnable with only an API token (no provider ssh block needed for a clone).
resource "proxmox_virtual_environment_vm" "vm" {
  name      = var.vm_name
  node_name = var.target_node
  vm_id     = var.vm_id
  tags      = ["terraform", "vsvc"]

  clone {
    vm_id = var.template_vm_id
  }

  # Requires qemu-guest-agent installed/enabled in the template; needed for IP discovery.
  agent {
    enabled = true
  }

  # Allow Terraform to stop a running VM during lifecycle changes.
  stop_on_destroy = true

  cpu {
    cores = var.vm_cores
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = var.vm_memory_mb
  }

  initialization {
    ip_config {
      ipv4 {
        address = var.ip_address
        gateway = var.ip_address == "dhcp" ? null : var.ip_gateway
      }
    }

    user_account {
      username = var.ci_username
      keys     = var.ci_ssh_public_keys
    }
  }

  network_device {
    bridge  = var.network_bridge
    vlan_id = var.vlan_id

    # SDN alternative: to attach the SDN vnet directly instead of tagging on vmbr0,
    # set network_bridge = "vsvc" and vlan_id = null.
  }

  operating_system {
    type = "l26"
  }
}
