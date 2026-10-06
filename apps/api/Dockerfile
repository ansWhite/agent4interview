FROM python:3.12-slim

WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages
RUN python -m pip install --no-cache-dir .[postgres]

EXPOSE 8000
# The container listens on its private interface; Compose publishes it only on host loopback.
CMD ["python", "-m", "uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
