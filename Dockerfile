FROM node:20-slim AS ui-builder

WORKDIR /build/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/       backend/
COPY data/          data/
COPY pipelines/     pipelines/
COPY ratio_engine/  ratio_engine/
COPY reporting/     reporting/
COPY valuation.py   ./
COPY main.py        ./
COPY ratio.py       ./

COPY coverage.txt           ./
COPY macro_config.json      ./
COPY ratio_profiles.json    ./
COPY sector_profiles.json   ./
COPY sector_assignments.json ./
COPY sector_overrides.json  ./
COPY valuation_profiles.json ./

COPY --from=ui-builder /build/ui/dist ui/dist/

RUN useradd --no-create-home --shell /bin/false appuser \
    && mkdir -p data logs .cache \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

CMD ["python", "backend/api.py"]
