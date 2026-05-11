FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "PyYAML>=6.0" \
    "scikit-learn>=1.5" \
    "numpy" \
    "pynput>=1.7" \
    "pytest>=8.0"

COPY . .

CMD ["python", "-m", "pytest", "tests/", "-v"]
