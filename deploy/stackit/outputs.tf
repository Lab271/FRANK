output "public_ip" {
  value = stackit_public_ip.frank.ip
}

output "url" {
  value = "https://${var.domain}"
}

output "server_id" {
  value = stackit_server.frank.server_id
}

output "data_volume_id" {
  description = "The data volume (/srv/frank), for a backup schedule outside the module."
  value       = stackit_volume.data.volume_id
}

output "store" {
  description = "FRANK_STORE, empty when the sightings stay on the volume."
  value       = local.store
}

output "create_token" {
  description = "Create the first token on the VM."
  value = var.admin_cidr == "" ? (
    "stackit server command create --project-id ${var.project_id} --server-id ${stackit_server.frank.server_id} --template-name RunShellScript --params script='podman exec frank frank token partner <label>'"
  ) : "ssh debian@${stackit_public_ip.frank.ip} sudo podman exec frank frank token partner <label>"
}
