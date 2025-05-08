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

variable "eventbridge_warmer_enabled" {
  type        = bool
  description = "Enable EventBridge warmer to try to keep Lambda functions warm. See https://aws.amazon.com/pt/blogs/compute/operating-lambda-performance-optimization-part-1/, \"Understanding how functions warmers work\""
  default     = false
}
