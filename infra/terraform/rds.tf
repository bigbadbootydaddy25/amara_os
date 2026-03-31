resource "aws_security_group" "rds" {
  name        = "amara-${var.env}-rds-sg"
  description = "Allow Postgres from within VPC"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "amara-${var.env}-rds-sg" }
}

resource "aws_db_subnet_group" "main" {
  name       = "amara-${var.env}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "amara-${var.env}-db-subnet-group" }
}

resource "aws_db_instance" "postgres" {
  identifier             = "amara-${var.env}-postgres"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.medium"
  allocated_storage      = 20
  storage_type           = "gp3"
  db_name                = "amara"
  username               = "amara"
  password               = var.db_password
  multi_az               = false
  publicly_accessible    = false
  skip_final_snapshot    = false
  final_snapshot_identifier = "amara-${var.env}-final"
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  tags = { Name = "amara-${var.env}-postgres" }
}

output "db_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "db_name" {
  value = aws_db_instance.postgres.db_name
}
