FROM python:3.13.9-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY backend/ecs_tasks/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ecs_tasks/worker/worker.py .
COPY backend/ecs_tasks/worker/template_engine.py .
COPY backend/ecs_tasks/worker/entrypoint.sh .

# Copy shared library (build context should be repo root)
COPY backend/shared /app/shared

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

# Health check: verify process exists AND health marker file is recent (< 2 min)
HEALTHCHECK --interval=30s --timeout=5s CMD \
  pgrep -f "python worker" && \
  find /tmp/worker_healthy -mmin -2 | grep -q . || exit 1

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"]
