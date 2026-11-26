FROM python:3.12-slim

WORKDIR /app
RUN printf '{"port": 3000, "healthcheck_path": "/ping"}\n' > /app/service_config.json
