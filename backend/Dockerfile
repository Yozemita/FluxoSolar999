FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app/backend
COPY requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt
RUN useradd --uid 10001 --create-home solar && mkdir /app/backend/data && chown solar:solar /app/backend/data
COPY --chown=solar:solar . /app/backend
USER solar
EXPOSE 8000
CMD ["sh", "/app/backend/start.sh"]
