variable "dnssec_enabled" {
  type        = bool
  description = "Enable DNSSEC"
  default     = true
}

variable "coordinator_memory_size" {
  type        = number
  description = "MPIC Coordinator Lambda Function Memory"
  default     = 256
}

variable "perspective_memory_size" {
  type        = number
  description = "MPIC Perspective Lambda Function Memory"
  default     = 256
}
