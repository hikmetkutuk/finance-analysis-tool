FROM node:20-slim AS ui-builder

WORKDIR /build/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build


FROM python:3.12-slim AS app-base

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/       backend/
COPY data/          data/
COPY pipelines/     pipelines/
COPY ratio_engine/  ratio_engine/
COPY reporting/     reporting/
COPY tests/         tests/
COPY valuation.py   ./
COPY main.py        ./
COPY ratio.py       ./

COPY tickers.txt            ./
COPY xu030.txt              ./
COPY macro_config.json      ./
COPY ratio_profiles.json    ./
COPY sector_profiles.json   ./
COPY sector_assignments.json ./
COPY sector_overrides.json  ./
COPY valuation_profiles.json ./
COPY company_metadata.json  ./
COPY sector_risk_config.json ./
COPY pyrightconfig.json       ./


FROM app-base AS validation

RUN pip install --no-cache-dir basedpyright ruff \
    && basedpyright \
    && ruff check . --select F401,I,UP,SIM113,SIM118,FURB188,B009,RUF100 \
    && python -m pytest -q \
    && touch /tmp/validation-complete


FROM app-base AS runtime

COPY --from=validation /tmp/validation-complete /tmp/validation-complete

COPY --from=ui-builder /build/ui/dist ui/dist/

RUN useradd --no-create-home --shell /bin/false appuser \
    && mkdir -p db data logs .cache \
    && chown -R appuser:appuser /app

USER appuser

ENV FLASK_HOST=0.0.0.0

EXPOSE 5000

CMD ["python", "-m", "backend.api"]
