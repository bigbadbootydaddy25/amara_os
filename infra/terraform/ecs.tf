data "aws_caller_identity" "current" {}

resource "aws_ecs_cluster" "main" {
  name = "amara-${var.env}"

  tags = { Name = "amara-${var.env}-cluster" }
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "amara-${var.env}-ecs-task-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_security_group" "ecs_tasks" {
  name        = "amara-${var.env}-ecs-tasks-sg"
  description = "ECS task traffic"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "amara-${var.env}-ecs-tasks-sg" }
}

locals {
  services = {
    api        = { port = 8080, image = var.api_image }
    dispatch   = { port = 8081, image = var.dispatch_image }
    propvision = { port = 8082, image = var.propvision_image }
    remote     = { port = 8083, image = var.remote_image }
  }
}

resource "aws_ecs_task_definition" "services" {
  for_each = local.services

  family                   = "amara-${var.env}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = each.key
    image     = each.value.image
    essential = true
    portMappings = [{
      containerPort = each.value.port
      protocol      = "tcp"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/amara-${var.env}-${each.key}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = { Name = "amara-${var.env}-${each.key}" }
}

resource "aws_cloudwatch_log_group" "services" {
  for_each          = local.services
  name              = "/ecs/amara-${var.env}-${each.key}"
  retention_in_days = 14
}

resource "aws_ecs_service" "services" {
  for_each = local.services

  name            = "amara-${var.env}-${each.key}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services[each.key].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = contains(["api", "propvision"], each.key) ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.services[each.key].arn
      container_name   = each.key
      container_port   = each.value.port
    }
  }

  depends_on = [aws_iam_role_policy_attachment.ecs_task_execution]

  tags = { Name = "amara-${var.env}-${each.key}" }
}

resource "aws_security_group" "alb" {
  name        = "amara-${var.env}-alb-sg"
  description = "ALB public traffic"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "amara-${var.env}-alb-sg" }
}

resource "aws_lb" "api" {
  name               = "amara-${var.env}-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = { Name = "amara-${var.env}-api-alb" }
}

resource "aws_lb_target_group" "services" {
  for_each = toset(["api", "propvision"])

  name        = "amara-${var.env}-${each.key}-tg"
  port        = local.services[each.key].port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }

  tags = { Name = "amara-${var.env}-${each.key}-tg" }
}

resource "aws_lb_listener" "api_http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services["api"].arn
  }
}
