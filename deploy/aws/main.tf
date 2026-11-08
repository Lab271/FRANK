# FRANK's storage on AWS (#220, ADR-019): a sketch, not a deployment.
#
# What it makes: the versioned bucket for the sightings and the audit log,
# the task role that may use it, and the EFS for the state that stays on a
# volume (the WAL, iocs.db, registry.db, participants.db, lists, geo files).
# What it leaves to the ECS/Fargate stack (spec 030): cluster, ALB, task
# definition, subnets, security groups. The task definition takes
# `task_environment` below and mounts the EFS at /data and /participants.
#
# ONE WRITER: FRANK holds a lease on the bucket but its WAL and the SQLite
# files live on the EFS. Run desired_count = 1 with
# deployment_minimum_healthy_percent = 0 and deployment_maximum_percent = 100,
# so a new task starts only after the old one has stopped. The 2-10 task
# scaling in spec 030 does not apply to FRANK.
#
# Credentials: the task role, through the AWS chain. No keys in the image
# or the task definition.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

variable "name" {
  description = "Prefix for the resources."
  type        = string
  default     = "frank"
}

variable "bucket_name" {
  description = "Globally unique name of the bucket."
  type        = string
}

variable "retention_days" {
  description = "FRANK_RETENTION_DAYS. The lifecycle rule backs it up: objects older than this plus the margin are removed by S3 even if FRANK is down."
  type        = number
  default     = 400
}

variable "lifecycle_margin_days" {
  description = "Days past the retention before the lifecycle rule removes an object."
  type        = number
  default     = 30
}

variable "noncurrent_days" {
  description = "Days a replaced or deleted object version is kept (versioning protects the manifest and the audit log from a bad write)."
  type        = number
  default     = 30
}

variable "subnet_ids" {
  description = "Private subnets of the tasks, one EFS mount target in each."
  type        = list(string)
}

variable "task_security_group_id" {
  description = "Security group of the FRANK tasks; allowed to reach the EFS on 2049."
  type        = string
}

variable "vpc_id" {
  type = string
}

# --- Bucket -----------------------------------------------------------------

resource "aws_s3_bucket" "frank" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "frank" {
  bucket                  = aws_s3_bucket.frank.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "frank" {
  bucket = aws_s3_bucket.frank.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frank" {
  bucket = aws_s3_bucket.frank.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "frank" {
  bucket     = aws_s3_bucket.frank.id
  depends_on = [aws_s3_bucket_versioning.frank]

  rule {
    id     = "retention-backstop"
    status = "Enabled"
    filter {}
    expiration {
      days = var.retention_days + var.lifecycle_margin_days
    }
    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# --- Task role --------------------------------------------------------------

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "List"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.frank.arn]
  }
  statement {
    sid       = "Objects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.frank.arn}/*"]
  }
}

resource "aws_iam_role_policy" "bucket" {
  name   = "bucket"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.bucket.json
}

# --- EFS: the state that stays on a volume ----------------------------------

resource "aws_efs_file_system" "state" {
  creation_token = "${var.name}-state"
  encrypted      = true
  tags           = { Name = "${var.name}-state" }
}

resource "aws_security_group" "efs" {
  name_prefix = "${var.name}-efs-"
  vpc_id      = var.vpc_id
  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [var.task_security_group_id]
  }
}

resource "aws_efs_mount_target" "state" {
  for_each        = toset(var.subnet_ids)
  file_system_id  = aws_efs_file_system.state.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}

# FRANK runs as uid/gid 65532 and keeps its SQLite files and WAL here.
resource "aws_efs_access_point" "data" {
  file_system_id = aws_efs_file_system.state.id
  posix_user {
    uid = 65532
    gid = 65532
  }
  root_directory {
    path = "/frank"
    creation_info {
      owner_uid   = 65532
      owner_gid   = 65532
      permissions = "0750"
    }
  }
}

# --- For the task definition ------------------------------------------------

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "efs_file_system_id" {
  value = aws_efs_file_system.state.id
}

output "efs_access_point_id" {
  value = aws_efs_access_point.data.id
}

# No endpoint: AWS S3, over HTTPS (the image has the `tls` feature). The
# region comes from the task's AWS_REGION. The audit log goes to the same
# bucket, under the prefix.
output "task_environment" {
  value = {
    FRANK_STORE          = "s3://${aws_s3_bucket.frank.bucket}/sightings"
    FRANK_RETENTION_DAYS = tostring(var.retention_days)
  }
}
