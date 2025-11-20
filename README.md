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

## Code Quality

This project uses automated code quality tools to maintain consistent code style and catch issues early. All tools are configured in `pyproject.toml` and run automatically via pre-commit hooks.

### Formatting with Black

Black is used for automatic code formatting with a line length of 100 characters.

**Format all files:**