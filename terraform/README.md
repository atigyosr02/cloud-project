# Terraform

Terraform infrastructure for MediCare will be defined in this directory.

The AWS deployment described in the project README is the intended starting point:

- VPC networking with public load-balancer subnets and private application/database subnets
- An HTTPS load balancer in front of the application
- An application host or service with an IAM role for private S3 access
- PostgreSQL on RDS and a private S3 bucket for documents
- Runtime secrets supplied through AWS Secrets Manager

No infrastructure resources are defined yet. Add environment-specific variable values outside version control, review the plan carefully, and do not commit Terraform state or secret values.

Typical workflow after adding Terraform configuration:

```sh
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan
```

Do not run `terraform apply` until the account, region, network exposure, and expected AWS costs have been reviewed.