terraform {
  required_version = ">= 1.6"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.107"
    }
  }

  # HCP Terraform (production): uncomment and set org/workspace, then run `terraform init`.
  # Keep it commented so local `terraform init -backend=false` + `validate` works offline.
  # When enabled, set proxmox_api_token as a sensitive workspace variable (or variable set),
  # never in repo files.
  # cloud {
  #   organization = "ncdv"
  #   workspaces {
  #     name = "d3hl-managed-proxmox-vm"
  #   }
  # }
}

provider "proxmox" {
  endpoint = var.proxmox_endpoint

  # Format: "USER@REALM!TOKENID=SECRET". Injected at runtime from 1Password, e.g.:
  #   export TF_VAR_proxmox_api_token="$(op read 'op://d3HLPRV/Proxmox API for AI/username')=$(op read 'op://d3HLPRV/Proxmox API for AI/credential')"
  # Never commit the resolved value.
  api_token = var.proxmox_api_token

  # PVE uses a self-signed certificate on the cluster endpoint.
  insecure = var.proxmox_insecure

  # NOTE: a clone-based VM needs no `ssh {}` block. Add one only for provider operations that
  # require node SSH access (file uploads, disk `import_from`, etc.).
}
