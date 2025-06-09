# ── build stage ─────────────────────────────────────────────
FROM python:3.11-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install -r requirements.txt

# ── runtime stage ───────────────────────────────────────────
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PORT=10000
WORKDIR /app
COPY --from=build /install /usr/local
COPY . .

EXPOSE 10000                     # tells Render which port to publish
CMD ["gunicorn", "--bind", "0.0.0.0:10000",
     "HotSpringWebApp.HotSpringWebApp:app"]
