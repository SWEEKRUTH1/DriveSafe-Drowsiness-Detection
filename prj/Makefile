# Makefile for DriveSafe

.PHONY: help install setup run test clean docker docker-run docker-compose-up docker-compose-down lint format

help:
	@echo "DriveSafe Project - Available Commands"
	@echo "======================================"
	@echo ""
	@echo "Development:"
	@echo "  make install          - Install dependencies"
	@echo "  make setup            - Setup models and environment"
	@echo "  make run              - Run Streamlit application"
	@echo "  make test             - Run component tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             - Run linter (pylint)"
	@echo "  make format           - Format code (black)"
	@echo "  make clean            - Clean temporary files"
	@echo ""
	@echo "Docker:"
	@echo "  make docker           - Build Docker image"
	@echo "  make docker-run       - Run Docker container"
	@echo "  make docker-compose-up   - Start docker-compose services"
	@echo "  make docker-compose-down - Stop docker-compose services"
	@echo ""

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

setup:
	@echo "Setting up models..."
	python setup_models.py
	@echo "Setup complete!"

run:
	@echo "Starting DriveSafe application..."
	streamlit run app.py

test:
	@echo "Running component tests..."
	python test_components.py

lint:
	@echo "Running pylint..."
	pylint modules/*.py app.py config.py utils.py || true

format:
	@echo "Formatting code with black..."
	black modules/ app.py config.py utils.py

clean:
	@echo "Cleaning temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage htmlcov/
	@echo "Clean complete!"

docker:
	@echo "Building Docker image..."
	docker build -t drivesafe:latest .
	@echo "Docker image built!"

docker-run:
	@echo "Running Docker container..."
	docker run -it --device /dev/video0 -p 8501:8501 drivesafe:latest

docker-compose-up:
	@echo "Starting docker-compose services..."
	docker-compose up -d
	@echo "Services started! Access at http://localhost:8501"

docker-compose-down:
	@echo "Stopping docker-compose services..."
	docker-compose down

# Development server with auto-reload
dev:
	@echo "Starting development server..."
	streamlit run app.py --logger.level=debug

# Run all checks before commit
check: lint test
	@echo "All checks passed!"

# Quick setup for new environment
quickstart: install setup
	@echo "Quickstart complete! Run 'make run' to start the application"

.DEFAULT_GOAL := help
