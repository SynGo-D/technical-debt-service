# Runtime for the technical debt service.
#
# Much plainer than analysis-engine's image: this service shells out to
# nothing. It reads analysis-engine's database, calls an OpenAI-compatible
# endpoint over HTTPS, and writes its own tables — so it needs Python and
# the certificate store, and no language toolchains at all.
FROM python:3.12-slim

WORKDIR /app

# Dependencies first, so this layer is reused whenever only source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Run as a non-root user. The service writes nothing to disk, so it needs
# no writable paths and there is no reason to give it root.
RUN useradd --create-home --uid 10001 debt
USER debt

EXPOSE 5003

# `src.main:app`, matching how the service is run locally — src/ is a
# package here rather than an installed distribution.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5003"]
