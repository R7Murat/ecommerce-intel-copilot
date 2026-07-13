variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "groq_api_key" {
  type      = string
  sensitive = true
}

variable "gemini_api_key" {
  type      = string
  sensitive = true
}

variable "image_tag" {
  type    = string
  default = "latest"
}