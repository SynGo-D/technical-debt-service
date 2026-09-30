# Runtime for the technical debt service.
#
# Much plainer than analysis-engine's image: this service shells out to
# nothing. It reads analysis-engine's database, calls an OpenAI-compatible
# endpoint over HTTPS, and writes its own tables — so it needs Python and
# the certificate store, and no language toolchains at all.
FROM python:3.12-slim

# PYTHONUNBUFFERED matters in a container: without it Python buffers stdout
# when it is not a terminal, so logs arrive in blocks or not at all when a
# container is killed — which is exactly when they are wanted.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so this layer is reused whenever only source changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY src/ ./src/

# Run as a non-root user. The service writes nothing to disk, so it needs
# no writable paths and there is no reason to give it root.
#
# 10001 rather than 1000: the first ordinary user on most hosts is 1000, so
# a bind mount would hand this process that person's ownership.
RUN useradd --create-home --uid 10001 debt
USER debt

EXPOSE 5003

# `src.main:app`, matching how the service is run locally — src/ is a
# package here rather than an installed distribution.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5003"]
