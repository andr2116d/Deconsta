resource "random_id" "sufijo" {
  byte_length = 4
}

# Documentos y comprobantes: la aplicación los cifra antes de subirlos.
resource "aws_s3_bucket" "archivos" {
  bucket = "deconsta-archivos-${random_id.sufijo.hex}"
}

# El código que se despliega en la instancia.
resource "aws_s3_bucket" "despliegue" {
  bucket        = "deconsta-despliegue-${random_id.sufijo.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "archivos" {
  bucket                  = aws_s3_bucket.archivos.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "despliegue" {
  bucket                  = aws_s3_bucket.despliegue.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "codigo" {
  bucket = aws_s3_bucket.despliegue.id
  key    = "codigo.tar.gz"
  source = var.codigo
  etag   = filemd5(var.codigo)
}

# La aplicación pide claves de acceso al bucket (S3_ACCESS_KEY y S3_SECRET_KEY).
resource "aws_iam_user" "aplicacion" {
  name = "deconsta-aplicacion"
}

resource "aws_iam_user_policy" "aplicacion" {
  name = "archivos"
  user = aws_iam_user.aplicacion.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.archivos.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.archivos.arn
      },
    ]
  })
}

resource "aws_iam_access_key" "aplicacion" {
  user = aws_iam_user.aplicacion.name
}
