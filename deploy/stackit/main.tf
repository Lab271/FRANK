# FRANK on STACKIT (ADR-016): one VM running the FRANK container with
# podman, its data on a separate block volume that outlives the VM, and
# Caddy in front for TLS. Same image and on-disk layout as `make up`.

# By name: the distro/version filter also matches "Debian 13 ARM64", and
# the image is amd64 only ("flavor and image architecture do not match").
data "stackit_image_v2" "debian" {
  project_id = var.project_id
  name       = "Debian 13"
}

resource "stackit_network" "frank" {
  project_id         = var.project_id
  name               = var.name
  ipv4_prefix_length = 24
}

resource "stackit_security_group" "frank" {
  project_id = var.project_id
  name       = var.name
  stateful   = true
}

resource "stackit_security_group_rule" "ssh" {
  count             = var.admin_cidr == "" ? 0 : 1
  project_id        = var.project_id
  security_group_id = stackit_security_group.frank.security_group_id
  direction         = "ingress"
  ip_range          = var.admin_cidr
  protocol          = { name = "tcp" }
  port_range        = { min = 22, max = 22 }
}

resource "stackit_security_group_rule" "web" {
  for_each          = toset(["80", "443"])
  project_id        = var.project_id
  security_group_id = stackit_security_group.frank.security_group_id
  direction         = "ingress"
  ip_range          = "0.0.0.0/0"
  protocol          = { name = "tcp" }
  port_range        = { min = tonumber(each.value), max = tonumber(each.value) }
}

resource "stackit_network_interface" "frank" {
  project_id         = var.project_id
  network_id         = stackit_network.frank.network_id
  security_group_ids = [stackit_security_group.frank.security_group_id]
}

resource "stackit_public_ip" "frank" {
  project_id           = var.project_id
  network_interface_id = stackit_network_interface.frank.network_interface_id
}

resource "stackit_key_pair" "admin" {
  count      = var.ssh_public_key == "" ? 0 : 1
  name       = "${var.name}-admin"
  public_key = var.ssh_public_key
}

# The data: kept when the VM is replaced. `tofu destroy` refuses to
# remove it; take it out of the state first if you mean to.
resource "stackit_volume" "data" {
  project_id        = var.project_id
  name              = "${var.name}-data"
  availability_zone = var.availability_zone
  size              = var.data_volume_gb
  lifecycle {
    prevent_destroy = true
  }
}

resource "stackit_server" "frank" {
  project_id         = var.project_id
  name               = var.name
  machine_type       = var.machine_type
  availability_zone  = var.availability_zone
  keypair_name       = one(stackit_key_pair.admin[*].name)
  network_interfaces = [stackit_network_interface.frank.network_interface_id]
  # The STACKIT Server Agent runs server commands (RunShellScript), the way
  # in without SSH.
  agent = {
    provisioning_policy = "ALWAYS"
  }
  boot_volume = {
    source_type           = "image"
    source_id             = data.stackit_image_v2.debian.image_id
    size                  = 20
    delete_on_termination = true
  }
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    domain         = var.domain
    image          = var.image
    registry       = split("/", var.image)[0]
    registry_user  = var.registry_user
    registry_token = var.registry_token
    retention_days = var.retention_days
    store          = local.store
    store_key      = local.store == "" ? "" : stackit_objectstorage_credential.frank[0].access_key
    store_secret   = local.store == "" ? "" : stackit_objectstorage_credential.frank[0].secret_access_key
    abuse_key      = var.abuse_key
    # The same scripts as `make geoip` and `make lists` (#276).
    fetch_geoip = file("${path.module}/../../scripts/fetch-geoip.sh")
    fetch_lists = file("${path.module}/../../scripts/fetch-lists.sh")
    # OpenStack-style serial: the first 20 characters of the volume ID.
    data_disk = "/dev/disk/by-id/virtio-${substr(stackit_volume.data.volume_id, 0, 20)}"
  })
}

resource "stackit_server_volume_attach" "data" {
  project_id = var.project_id
  server_id  = stackit_server.frank.server_id
  volume_id  = stackit_volume.data.volume_id
}

# The sightings and the audit log in Object Storage (ADR-019): the WAL and
# the SQLite files stay on the data volume. FRANK signs with the
# credential's keys, which reach the VM through its user data.
locals {
  store = var.store_bucket == "" ? "" : "s3://${var.store_bucket}/sightings?endpoint=https://object.storage.${var.region}.onstackit.cloud&region=${var.region}"
}

# Every sighting and the audit log: a plan that would replace it (another
# name) or remove it (store_bucket emptied) is refused. Versioning keeps
# deleted objects, not a deleted bucket. To drop it on purpose, take it out
# of the state first and delete it in STACKIT.
resource "stackit_objectstorage_bucket" "frank" {
  count      = var.store_bucket == "" ? 0 : 1
  project_id = var.project_id
  name       = var.store_bucket
  lifecycle {
    prevent_destroy = true
  }
}

resource "stackit_objectstorage_credentials_group" "frank" {
  count      = var.store_bucket == "" ? 0 : 1
  project_id = var.project_id
  name       = var.name
}

resource "stackit_objectstorage_credential" "frank" {
  count                = var.store_bucket == "" ? 0 : 1
  project_id           = var.project_id
  credentials_group_id = stackit_objectstorage_credentials_group.frank[0].credentials_group_id
}
