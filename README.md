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