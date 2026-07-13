resource "aws_ecr_repository" "copilot" {
  name         = "ecommerce-intel-copilot"
  force_delete = true
}

resource "aws_iam_role" "apprunner_ecr_access" {
  name = "copilot-apprunner-ecr-access"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_apprunner_service" "copilot" {
  service_name = "ecommerce-intel-copilot"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }
    image_repository {
      image_identifier      = "${aws_ecr_repository.copilot.repository_url}:${var.image_tag}"
      image_repository_type = "ECR"
      image_configuration {
        port = "8080"
        runtime_environment_variables = {
          GROQ_API_KEY   = var.groq_api_key
          GEMINI_API_KEY = var.gemini_api_key
        }
      }
    }
    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu    = "2 vCPU"
    memory = "4 GB"
  }

  health_check_configuration {
    protocol            = "TCP"
    interval            = 10
    timeout             = 10
    healthy_threshold   = 1
    unhealthy_threshold = 10
  }
}