variable "region" {
  type    = string
  default = "us-east-1"
}

variable "entorno" {
  type    = string
  default = "produccion"
}

variable "tipo_instancia" {
  description = "CPU dedicada (sin créditos que se agoten) para el OCR; 8 GB de memoria como mínimo."
  type        = string
  default     = "c7i.2xlarge"
}

variable "ocr_concurrencia" {
  description = "Documentos de deudas que se analizan a la vez: un proceso de PaddleOCR por cada uno."
  type        = number
  default     = 2
}

variable "pagos_concurrencia" {
  description = "Vouchers de pago que se analizan a la vez, en su propio worker."
  type        = number
  default     = 2
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
