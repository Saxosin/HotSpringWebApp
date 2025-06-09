# ── build stage ────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install -r requirements.txt

# ── runtime stage ──────────────────────────────────────────
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PORT=10000

WORKDIR /app
# copy installed deps from the named build stage
COPY --from=builder /install /usr/local
COPY . .

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "HotSpringWebApp.HotSpringWebApp:app"]
