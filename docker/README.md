# Docker Setup for NLWeb

This project organizes Docker-related files in the `docker/` directory, providing a split Docker setup that allows you to:
1. Create a base image with all dependencies
2. Use the base image for both development and production environments

## Directory Structure

```
docker/
├── Dockerfile.base        # Base image with dependencies
├── Dockerfile.app         # Production application image (extends base)
├── Dockerfile.dev         # Development container image (extends base)
├── docker-compose.yaml    # Defines both production and development services
└── build-docker-images.sh # Script to build all docker images
```

## Building the Docker Images

Use the provided script to build all images:

```bash
./docker/build-docker-images.sh
```

This will create the following images:

| Image Tag | Description | Based On |
|-----------|-------------|----------|
| `nlweb-base:latest` | Base image with dependencies | `python:3.13-slim` |
| `nlweb:latest` | Production application image | `nlweb-base:latest` |
| `nlweb-dev:latest` | Development container image | `nlweb-base:latest` |

Each image serves a specific purpose in the development and deployment workflow, with both the application and development containers extending from the same base image to ensure consistency.

## Using Docker Compose

### For Production

To start the production container:

```bash
docker-compose -f docker/docker-compose.yaml up nlweb
```

### For Development

To start the development container:

```bash
docker-compose -f docker/docker-compose.yaml up nlweb-dev
```

You can then access the development container:

```bash
docker exec -it nlweb-dev bash
```

## Benefits of This Approach

1. **Consistency**: Development and production environments use the same base image
2. **Efficiency**: Dependencies are built once in the base image
3. **Maintainability**: Updates to dependencies only need to be made in one place
4. **Speed**: Development container builds faster since it uses the pre-built base image

## Development Container Features

The development container includes:
- Development tools (git, curl, vim, etc.)
- Testing frameworks (pytest, etc.)
- Code quality tools (flake8, black)
- Debugging support (debugpy)
- Full workspace mounted at `/workspace`
