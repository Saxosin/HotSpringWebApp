FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --prefix=/install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY --from=builder /install /usr/local
COPY . .

EXPOSE 10000
CMD ["gunicorn", "-b", "0.0.0.0:10000", "HotSpringWebApp:app"]
