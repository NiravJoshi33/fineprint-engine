provider "aws" {
  region = "eu-north-1"
  profile = "NiravJ"
}

resource "aws_ecr_repository" "fineprint" {
  name                 = "fineprint"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}