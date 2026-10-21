data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "random_bytes" "clave_datos" {
  length = 32
}

resource "random_bytes" "clave_huella" {
  length = 32
}

resource "random_bytes" "clave_archivos" {
  length = 32
}

resource "random_password" "postgres" {
  length  = 32
  special = false
}

resource "aws_iam_role" "instancia" {
  name = "deconsta-instancia"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instancia.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "codigo" {
  name = "codigo"
  role = aws_iam_role.instancia.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = "${aws_s3_bucket.despliegue.arn}/*"
    }]
  })
}

resource "aws_iam_instance_profile" "instancia" {
  name = "deconsta-instancia"
  role = aws_iam_role.instancia.name
}

locals {
  # Un nombre público sin comprar dominio: sslip.io resuelve a la IP elástica y Caddy obtiene el
  # certificado de Let's Encrypt para él.
  dominio = "${replace(aws_eip.web.public_ip, ".", "-")}.sslip.io"

  entorno = templatefile("${path.module}/plantillas/env.tftpl", {
    dominio           = local.dominio
    postgres          = random_password.postgres.result
    clave_datos       = random_bytes.clave_datos.base64
    clave_huella      = random_bytes.clave_huella.base64
    clave_archivos    = random_bytes.clave_archivos.base64
    region            = var.region
    bucket            = aws_s3_bucket.archivos.id
    s3_access_key     = aws_iam_access_key.aplicacion.id
    s3_secret_key     = aws_iam_access_key.aplicacion.secret
    anthropic_api_key = var.anthropic_api_key
  })
}

resource "aws_instance" "web" {
  ami                    = data.aws_ssm_parameter.ami.value
  instance_type          = var.tipo_instancia
  subnet_id              = aws_subnet.publica.id
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile   = aws_iam_instance_profile.instancia.name

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens = "required"
  }

  user_data = templatefile("${path.module}/plantillas/arranque.sh.tftpl", {
    entorno = local.entorno
    compose = file("${path.module}/plantillas/compose.yaml")
    bucket  = aws_s3_bucket.despliegue.id
    region  = var.region
  })
  user_data_replace_on_change = false

  tags = { Name = "deconsta" }

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

resource "aws_eip_association" "web" {
  instance_id   = aws_instance.web.id
  allocation_id = aws_eip.web.id
}
