# Story of My Life - Application Container
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (for layer caching)
COPY pyproject.toml .
COPY README.md .

# Create minimal package structure for pip install
RUN mkdir -p src/soml && \
    echo '__version__ = "0.1.0"' > src/soml/__init__.py

# Install dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy source code
COPY src/ src/
COPY scripts/ scripts/
COPY tests/ tests/

# Create data directories
RUN mkdir -p /data/{people,projects,goals,events,notes,memories,.deleted,.index}

# Set Python path
ENV PYTHONPATH=/app/src

# Default command
CMD ["python", "-m", "soml.cli"]

