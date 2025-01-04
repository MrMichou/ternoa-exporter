# Ternoa Blockchain Monitoring

## Table of Contents
- [About](#about)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Contributing](#contributing)
- [License](#license)

## About
Ternoa Monitoring is a comprehensive monitoring solution for the Ternoa blockchain, leveraging Prometheus for metrics collection and Grafana for visualization.

## Features
- Real-time blockchain metrics collection
- Prometheus time-series data storage
- Grafana dashboard visualization
- Dockerized deployment
- Custom metrics exporter

## Prerequisites
- Docker (v20.10 or later)
- Docker Compose (v1.29 or later)
- Git

## Installation

### Clone the Repository
```bash
git clone <repository-url>
cd ternoa-monitoring
```

### Start Services
```bash
docker-compose up -d
```

## Usage
- Prometheus Dashboard: http://localhost:9090
- Grafana Dashboard: http://localhost:3000
  - Default Credentials: admin/admin
- Metrics Endpoint: http://localhost:8000

## Project Structure
```
ternoa-monitoring/
│
├── exporter/
│   └── ternoa-exporter.py      # Custom metrics collection script
│
├── grafana/
│   ├── dashboards/              # Grafana dashboard configurations
│   └── provisioning/            # Datasource and plugin provisioning
│
├── prometheus/
│   └── prometheus.yml           # Prometheus configuration
│
├── Dockerfile.exporter          # Docker image for metrics exporter
├── docker-compose.yml           # Docker Compose configuration
└── requirements.txt             # Python dependencies
```

## Configuration

### Prometheus Configuration
Edit `prometheus/prometheus.yml` to modify:
- Scrape intervals
- Monitoring targets

### Grafana Configuration
- Dashboards located in `grafana/dashboards/`
- Provisioning settings in `grafana/provisioning/`

## Dependencies
- substrate-interface (v1.7.4)
- prometheus-client (v0.17.1)
- websockets (v11.0.3)

## Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License
Distributed under the MIT License. See `LICENSE` for more information.

## Contact
Project Maintainer - MrMichou/Michael N.

Ternoa Project - https://www.ternoa.network/

Ternoa Operator - https://ternoa.scove.io/
