output "vpc_id"      { value = aws_vpc.main.id }
output "db_endpoint" { value = aws_db_instance.postgres.endpoint }
output "api_alb_dns" { value = aws_lb.api.dns_name }
