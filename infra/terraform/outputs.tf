output "ecr_repository_url" {
  value = aws_ecr_repository.copilot.repository_url
}

output "service_url" {
  value = "https://${aws_apprunner_service.copilot.service_url}"
}