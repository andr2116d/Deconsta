output "url" {
  value = "https://${local.dominio}"
}

output "instancia_id" {
  value = aws_instance.web.id
}

output "bucket_despliegue" {
  value = aws_s3_bucket.despliegue.id
}
