# … build stage stays unchanged …

# ── runtime stage ───────────────────────────────────────────
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PORT=10000
WORKDIR /app
COPY --from=build /install /usr/local
COPY . .

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "HotSpringWebApp.HotSpringWebApp:app"]
