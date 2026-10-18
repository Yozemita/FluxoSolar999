# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt
RUN useradd --uid 10001 --create-home solar && mkdir /app/data && chown solar:solar /app/data
COPY --chown=solar:solar backend /app/backend
COPY --chown=solar:solar frontend /app/frontend
COPY --chown=solar:solar scripts /app/scripts
USER solar
EXPOSE 8000
CMD ["sh", "/app/scripts/start.sh"]
