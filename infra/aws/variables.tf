variable "region" {
  type    = string
  default = "us-east-1"
}

variable "entorno" {
  type    = string
  default = "produccion"
}

variable "tipo_instancia" {
  description = "PaddleOCR necesita memoria: 8 GB como mínimo."
  type        = string
  default     = "t3.large"
}

variable "codigo" {
  description = "Ruta local del tar.gz del repositorio (git archive) que se despliega."
  type        = string
}

variable "anthropic_api_key" {
  description = "Clave de la Claude Console. Vacía: la revisión con IA queda incompleta."
  type        = string
  default     = ""
  sensitive   = true
}
