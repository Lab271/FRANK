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

variable "abuse_key" {
  description = "abuse.ch Auth-Key for the URLhaus and ThreatFox lists; empty skips them (the other lists are fetched without it)."
  type        = string
  default     = ""
  sensitive   = true
}

# SSO (ADR-020, test-frank#2): all four or none. Empty keeps sign-in by
# token only. The redirect URL is https://<domain>/v1/sso/callback.
variable "sso_issuer" {
  description = "OIDC issuer, e.g. https://<org>.okta.com/oauth2/default (FRANK_SSO_ISSUER); empty turns SSO off."
  type        = string
  default     = ""
}

variable "sso_client_id" {
  description = "The OIDC application's client id (FRANK_SSO_CLIENT_ID)."
  type        = string
  default     = ""
}

variable "sso_client_secret" {
  description = "The OIDC application's client secret; reaches FRANK as a file (FRANK_SSO_CLIENT_SECRET_FILE), never as an environment variable."
  type        = string
  default     = ""
  sensitive   = true
}

variable "sso_organisation" {
  description = "The organisation (it must exist before SSO is turned on) that people signing in for the first time are created in (FRANK_SSO_ORGANISATION)."
  type        = string
  default     = ""
}
