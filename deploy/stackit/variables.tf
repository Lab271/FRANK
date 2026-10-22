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
  description = "Admin SSH public key."
  type        = string
}

variable "admin_cidr" {
  description = "Source range allowed to SSH in."
  type        = string
}

variable "domain" {
  description = "DNS name pointing at the public IP; Caddy gets a certificate for it."
  type        = string
}

variable "image" {
  description = "FRANK container image."
  type        = string
  default     = "ghcr.io/lab271/frank:latest"
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
