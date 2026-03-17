FROM python:3.12-slim

ARG VERSION=0.0.1
ENV CASPER_VERSION=$VERSION

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
  && apt-get install -y --no-install-recommends \
    gcc \
    libnetcdf-dev \
  && pip install --no-cache-dir --upgrade \
    pip \
    cython \
    uv \
    virtualenv \
  && apt-get purge -y --auto-remove gcc \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

RUN adduser --quiet --disabled-password --shell /bin/sh \
  --home /home/dockeruser --gecos "" --uid 1000 dockeruser

RUN mkdir -p /worker && chown dockeruser:dockeruser /worker

WORKDIR /worker

# ✅ Copy EVERYTHING needed for build (including source)
COPY --chown=dockeruser:dockeruser pyproject.toml uv.lock README.md LICENSE ./
COPY --chown=dockeruser:dockeruser casper ./casper

USER dockeruser

# ✅ Now build works because package exists
RUN uv sync --extra harmony --frozen --no-editable

COPY --chown=dockeruser:dockeruser docker-entrypoint.sh ./

RUN chmod +x ./docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]