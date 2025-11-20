# HFT Trading Bot with MQL Compiler

A high-frequency trading bot designed for 5-15 minute timeframes, featuring real-time market data processing, MQL strategy compilation, and comprehensive risk management. Built with FastAPI for high-performance async operations and scalable architecture.

## Overview

This trading bot provides a complete infrastructure for algorithmic trading with the following key features:

- **Real-time Data Pipeline**: WebSocket-based market data ingestion with Redis caching
- **MQL Compiler Integration**: Execute MetaTrader strategies in Python environment
- **Risk Management System**: Position sizing, stop-loss automation, and exposure monitoring
- **FastAPI Backend**: High-performance async API for strategy management and monitoring
- **PostgreSQL Storage**: Persistent storage for trades, strategies, and historical data
- **Scalable Architecture**: Modular design supporting multiple trading strategies simultaneously

## Prerequisites

Before setting up the project, ensure you have the following installed:

- **Python 3.11+** (Python 3.11 or 3.12 required)
- **Redis** (for caching and real-time data operations)
- **PostgreSQL** (for persistent data storage)
- **Git** (for version control)

## Setup Instructions

### 1. Clone the Repository

## Docker Setup

Docker provides a consistent and isolated environment for running the HFT Trading Bot across all platforms. This section covers building, running, and managing the application using Docker.

### Prerequisites

- **Docker 20.10+** (Docker Engine or Docker Desktop)
- **Docker Compose 2.0+** (included with Docker Desktop)

Verify your installation:

## Kubernetes Deployment

Deploy the HFT Trading Bot to Kubernetes clusters with production-ready configurations including auto-scaling, high availability, and zero-downtime updates.

### Prerequisites

- **kubectl 1.24+** (Kubernetes command-line tool)
- **Access to a Kubernetes cluster** (GKE, EKS, AKS, or self-managed)
- **cert-manager** (for automatic TLS certificate management)
- **NGINX Ingress Controller** (for external access and rate limiting)

Verify your cluster access:

## CI/CD Pipeline

The project uses GitHub Actions for automated testing, security scanning, and deployment to Kubernetes environments. The CI/CD pipeline ensures code quality, security compliance, and reliable deployments across development, staging, and production environments.

### Overview

The CI/CD pipeline consists of two main workflows:

- **CI Workflow** (`.github/workflows/ci.yml`): Runs automated tests, code quality checks, and security scans on every pull request
- **Deploy Workflow** (`.github/workflows/deploy.yml`): Builds Docker images and deploys to Kubernetes clusters when code is merged to main

### CI Workflow

The CI workflow runs automatically on pull requests and includes:

**Testing:**
- Runs pytest with coverage reporting
- Uploads coverage reports to Codecov
- Requires minimum test coverage thresholds

**Code Quality:**
- Black formatting checks
- Ruff linting for code quality
- Mypy static type checking

**Security Scanning:**
- pip-audit for dependency vulnerability scanning
- Trivy filesystem scanning for security issues
- Results uploaded to GitHub Security tab

All CI checks must pass before a pull request can be merged to the main branch.

### Deployment Workflow

The deployment workflow triggers automatically when code is merged to main and follows a progressive deployment strategy:

**Build Stage:**
- Builds Docker image with multi-stage optimization
- Pushes image to GitHub Container Registry (ghcr.io)
- Tags image with commit SHA and branch name
- Uses layer caching for faster builds

**Development Deployment:**
- Automatically deploys to development environment
- Updates Kubernetes deployment with new image
- Waits for rollout completion (10 minute timeout)
- Verifies health endpoint availability
- Automatically rolls back on failure

**Staging Deployment:**
- Deploys after successful development deployment
- Requires manual approval in GitHub UI
- Performs extended health checks
- Sends Slack notifications on success/failure

**Production Deployment:**
- Deploys after successful staging deployment
- Requires manual approval with additional reviewers
- Includes 2-minute monitoring period
- Runs extended health checks (10 iterations)
- Creates GitHub release on success
- Automatically rolls back on any failure

### Required Secrets

Configure the following secrets in your GitHub repository settings (Settings → Secrets and variables → Actions):

**Kubernetes Configuration:**
- `KUBE_CONFIG_DEV`: Base64-encoded kubeconfig for development cluster
- `KUBE_CONFIG_STAGING`: Base64-encoded kubeconfig for staging cluster
- `KUBE_CONFIG_PROD`: Base64-encoded kubeconfig for production cluster

**Notifications:**
- `SLACK_WEBHOOK`: Slack webhook URL for deployment notifications

To encode your kubeconfig:

## API Documentation

The HFT Trading Bot provides a comprehensive REST API built with FastAPI, offering automatic OpenAPI documentation, real-time health monitoring, and extensible endpoints for trading operations.

### API Overview

The API is built on **FastAPI**, a modern, high-performance web framework that provides:

- **Automatic OpenAPI Documentation**: Interactive API documentation at `/docs` (Swagger UI) and `/redoc` (ReDoc)
- **Type Safety**: Request/response validation using Pydantic models
- **Async Support**: High-performance async operations for concurrent request handling
- **WebSocket Support**: Real-time data streaming for market updates and trading signals
- **CORS Enabled**: Configured for frontend access with customizable origins

### Running the API

**Local Development with Uvicorn:**

## Database Setup

The HFT Trading Bot uses PostgreSQL for persistent storage of trading data, with SQLAlchemy 2.0 for async database operations and Alembic for schema migrations.

### Database Requirements

**PostgreSQL Version:**
- **PostgreSQL 15+** recommended for optimal performance and features
- Supports JSONB columns for flexible metadata storage
- Requires `uuid-ossp` extension for UUID generation

**Connection String Format:**