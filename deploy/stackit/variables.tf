variable "project_id" {
  description = "STACKIT project ID."
  type        = string
}

variable "region" {
  type    = string
  default = "eu01"
}

variable "availability_zone" {
  type    = string
  default = "eu01-1"
}

variable "name" {
  description = "Prefix for every resource."
  type        = string
  default     = "frank"
}

variable "machine_type" {
  type    = string
  default = "g2i.2"
}

variable "data_volume_gb" {
  description = "Size of the persistent data volume (sightings/ and iocs.db)."
  type        = number
  default     = 50
}

variable "ssh_public_key" {
  description = "Admin SSH public key; empty for none."
  type        = string
  default     = ""
}

variable "admin_cidr" {
  description = "Source range allowed to SSH in; empty opens no SSH port (reach the VM with server commands)."
  type        = string
  default     = ""
}

variable "domain" {
  description = "DNS name pointing at the public IP; Caddy gets a certificate for it."
  type        = string
}

variable "image" {
  description = "FRANK container image, pinned by commit: ghcr.io/lab271/frank:<sha>."
  type        = string
}

variable "registry_user" {
  description = "Registry user for a private image (empty for a public one)."
  type        = string
  default     = ""
}

variable "registry_token" {
  description = "Read-only registry token for a private image."
  type        = string
  default     = ""
  sensitive   = true
}

variable "retention_days" {
  type    = number
  default = 400
}

variable "store_bucket" {
  description = "Object Storage bucket for the sightings and the audit log (FRANK_STORE); empty keeps them on the data volume."
  type        = string
  default     = ""
}
