# ---- Stage 1: build ----
FROM python:3.14-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.14-slim
WORKDIR /app

RUN useradd --create-home appuser
COPY --from=builder /install /usr/local
COPY app/ ./app/

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
