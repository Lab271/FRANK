output "public_ip" {
  value = stackit_public_ip.frank.ip
}

output "url" {
  value = "https://${var.domain}"
}

output "create_token" {
  description = "Create the first token on the VM."
  value       = "ssh debian@${stackit_public_ip.frank.ip} sudo podman exec frank frank token partner <label>"
}
