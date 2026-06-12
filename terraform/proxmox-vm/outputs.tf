output "vm_id" {
  description = "Proxmox VM id of the created VM."
  value       = proxmox_virtual_environment_vm.vm.vm_id
}

output "vm_name" {
  description = "Name of the created VM."
  value       = proxmox_virtual_environment_vm.vm.name
}

output "vm_ipv4_addresses" {
  description = "IPv4 addresses reported by the qemu guest agent (empty until the agent is up)."
  value       = proxmox_virtual_environment_vm.vm.ipv4_addresses
}
