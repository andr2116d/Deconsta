data "aws_availability_zones" "disponibles" {
  state = "available"
}

resource "aws_vpc" "principal" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "deconsta" }
}

resource "aws_internet_gateway" "principal" {
  vpc_id = aws_vpc.principal.id
}

resource "aws_subnet" "publica" {
  vpc_id                  = aws_vpc.principal.id
  cidr_block              = "10.20.1.0/24"
  availability_zone       = data.aws_availability_zones.disponibles.names[0]
  map_public_ip_on_launch = true
  tags                    = { Name = "deconsta-publica" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.principal.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.principal.id
  }
}

resource "aws_route_table_association" "publica" {
  subnet_id      = aws_subnet.publica.id
  route_table_id = aws_route_table.publica.id
}

# Solo la web: la administración va por SSM, sin SSH abierto.
resource "aws_security_group" "web" {
  name   = "deconsta-web"
  vpc_id = aws_vpc.principal.id

  ingress {
    description = "HTTP (redirige a HTTPS y valida el certificado)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
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
}

resource "aws_eip" "web" {
  domain = "vpc"
  tags   = { Name = "deconsta" }
}
