FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src

# Run as a non-root user.
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 5003

# Configuration (DATABASE_URL, LLM_API_KEY, ...) comes from environment
# variables at runtime - no .env file is baked into the image.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5003"]
