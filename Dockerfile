# Build stage

FROM python:3.13-slim AS build
WORKDIR /build
RUN pip install build
COPY pyproject.toml README.md /build
COPY src/ /build/src
RUN python -m build -w /build


# Default stage

FROM python:3.13-slim
COPY --from=build /build/dist/*.whl /app/
RUN pip install --no-cache-dir /app/*.whl

EXPOSE 5000
CMD ["python", "-m", "doll"]
