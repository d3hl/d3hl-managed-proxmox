variable "proxmox_endpoint" {
  description = "Proxmox VE API endpoint."
  type        = string
  default     = "https://10.10.10.10:8006"
}

variable "proxmox_api_token" {
  description = "Proxmox API token in 'USER@REALM!TOKENID=SECRET' form. Inject from 1Password at runtime; never commit."
  type        = string
  sensitive   = true
}

variable "proxmox_insecure" {
  description = "Skip TLS verification for the self-signed PVE endpoint certificate."
  type        = bool
  default     = true
}

variable "target_node" {
  description = "Proxmox node to place the VM on (nodeA/nodeB/nodeD/nodeF)."
  type        = string
  default     = "nodeA"
}

variable "template_vm_id" {
  description = "VM id of the existing template to clone (see PVE-TEMPLATE-001). No default; must be provided."
  type        = number
}

variable "vm_id" {
  description = "VM id for the new clone."
  type        = number
  default     = 9001
}

variable "vm_name" {
  description = "Name for the new VM."
  type        = string
  default     = "tf-demo-vsvc"
}

variable "vm_cores" {
  description = "Number of CPU cores."
  type        = number
  default     = 2
}

variable "vm_memory_mb" {
  description = "Dedicated memory in MB."
  type        = number
  default     = 2048
}

variable "network_bridge" {
  description = "Bridge to attach the VM NIC to. vmbr0 is the VLAN-aware base bridge; set to an SDN vnet (e.g. vsvc) to drop vlan_id."
  type        = string
  default     = "vmbr0"
}

variable "vlan_id" {
  description = "VLAN tag for the NIC when using the VLAN-aware bridge. 30 = VM_SERVICES (vsvc). Set to null when attaching an SDN vnet directly."
  type        = number
  default     = 30
}

variable "ip_address" {
  description = "Cloud-init IPv4 address in CIDR form (e.g. 10.10.30.50/24) or \"dhcp\"."
  type        = string
  default     = "dhcp"
}

variable "ip_gateway" {
  description = "Cloud-init IPv4 gateway. Ignored when ip_address is \"dhcp\". VM_SERVICES gateway is 10.10.30.2."
  type        = string
  default     = "10.10.30.2"
}

variable "ci_username" {
  description = "Cloud-init user account username."
  type        = string
  default     = "ubuntu"
}

variable "ci_ssh_public_keys" {
  description = "Cloud-init authorized SSH public keys."
  type        = list(string)
  default     = []
}
