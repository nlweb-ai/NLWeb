# NLWeb Docker Setup

This repository contains a modular Docker setup for building and running the NLWeb application, which turns your website into a knowledge base.

## Docker Architecture

The Docker setup is organized into multiple files:

1. **Base Image (`docker/Dockerfile.base`)**: Contains all dependencies and build tools
2. **Application Image (`docker/Dockerfile.app`)**: Extends the base image for production use

The base image (`nlweb-base`) is used directly for development containers, while the application image is used for production.

This split architecture provides several benefits:
- **Reusability**: The base image is reused for both production and development
- **Consistency**: Development and production environments share the same core dependencies
- **Efficiency**: Updating dependencies only requires rebuilding the base image
- **Flexibility**: Development and production configurations can be maintained separately

### Platform Compatibility

When built using the multi-architecture build instructions, the Docker image can run on both:
- ARM64 architecture (e.g., Apple Silicon, AWS Graviton, Raspberry Pi)
- AMD64/x86_64 architecture (e.g., Intel, AMD)

This ensures that the image can be deployed on a wide range of hardware platforms without compatibility issues.

## Security

The Docker image includes several security features:
- System packages are updated to the latest versions during both build and runtime stages to address security vulnerabilities
- Minimal base image (python:3.10-slim) is used to reduce attack surface
- Non-root user is used to run the application
- Only necessary packages are installed with `--no-install-recommends` flag to minimize image size
- Package caches are cleaned up after installation to reduce image size

## Building the Docker Images

### Using the Build Script

The easiest way to build all Docker images is to use the provided build script:

```bash
./docker/build-docker-images.sh
```

This script builds two images:
- `nlweb-base:latest` (base image with dependencies, also used for development)
- `nlweb:latest` (production application image)

### Building Images Individually

You can also build the images individually:

```bash
# Build the base image (also used for development)
docker build -t nlweb-base:latest -f docker/Dockerfile.base .

# Build the application image
docker build -t nlweb:latest -f docker/Dockerfile.app .
```

### Multi-Architecture Build

For multi-architecture builds (ARM64 and AMD64), you can use Docker's buildx feature:

```bash
# For the base image
docker buildx build --platform linux/amd64,linux/arm64 -t nlweb-base:latest -f docker/Dockerfile.base --push .

# For the application image
docker buildx build --platform linux/amd64,linux/arm64 -t nlweb:latest -f docker/Dockerfile.app --push .
```

Note: The `--push` flag is required for multi-architecture builds. If you want to build without pushing to a registry, you can use the `--load` flag instead, but it only works for single-platform builds.

## Running the Docker Container

To run the Docker container:

```bash
docker run -p 8000:8000 -v ./code/config:/app/config:ro -v ./data:/data nlweb:latest
```

This will start the NLWeb application and expose it on port 8000.

## Configuration

### Environment Variables

The application requires several environment variables to be set. There are two ways to configure these variables:

1. **Using a `.env` file (recommended for local development):**

   When using `docker-compose.yaml`, the environment variables defined in the `code/.env` file are automatically loaded via the `env_file` directive. Ensure your `.env` file contains the required variables:

   ```env
   AZURE_VECTOR_SEARCH_ENDPOINT=https://your-search.search.windows.net
   AZURE_VECTOR_SEARCH_API_KEY=your-api-key
   OPENAI_API_KEY=your-openai-key
docker run -it -p 8000:8000 \
  -v ./data:/data \
  -v ./code/config:/app/code/config:ro \
  -e AZURE_VECTOR_SEARCH_ENDPOINT=${AZURE_VECTOR_SEARCH_ENDPOINT} \
  -e AZURE_VECTOR_SEARCH_API_KEY=${AZURE_VECTOR_SEARCH_API_KEY} \
  -e OPENAI_API_KEY=${OPENAI_API_KEY} \
  nlweb:latest
```

This command exports all non-commented variables from the code/.env file to your current shell session. However, for Docker deployments, it's recommended to pass environment variables directly to the container as shown above.

### Required Environment Variables

The following environment variables are required:

- `AZURE_VECTOR_SEARCH_ENDPOINT`: Your Azure Vector Search endpoint
- `AZURE_VECTOR_SEARCH_API_KEY`: Your Azure Vector Search API key
- `OPENAI_API_KEY`: Your OpenAI API key

See the `.env.template` file in the code directory for all available configuration options, but remember to pass them as environment variables rather than using a .env file.

## Using Docker Compose

This repository includes a [docker-compose.yaml](../docker/docker-compose.yaml) file for easy deployment of the NLWeb application.

### Running with Docker Compose

To start the production application using Docker Compose:

```bash
docker-compose -f docker/docker-compose.yaml up nlweb -d
```

To stop the application:

```bash
docker-compose -f docker/docker-compose.yaml down
```

Note: The `-d` flag runs containers in detached mode (in the background). Omit this flag if you want to see the output in your terminal.

### Configuration with Docker Compose

The `docker-compose.yaml` file is configured to automatically use environment variables from the `code/.env` file. This means you don't need to set environment variables in your shell or create a separate `.env` file in the same directory as the `docker-compose.yaml` file.

Simply make sure your `code/.env` file contains the necessary environment variables:

```
AZURE_VECTOR_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_VECTOR_SEARCH_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-openai-key
OPENAI_API_KEY=your-openai-key
```

Docker Compose will automatically load these variables from the `code/.env` file when you run:

```bash
docker-compose -f docker/docker-compose.yaml up nlweb -d
```

### Data Persistence with Docker Compose

The `docker-compose.yaml` file is configured with the following volume mounts:

1. **Data Directory**: Mounts the `./data` directory from your host to `/app/data` in the container. This allows data to persist between container restarts.

2. **Configuration Directory**: Mounts the `./code/config` directory from your host to `/app/config` in the container as read-only. This provides access to configuration files without allowing the container to modify them, ensuring configuration integrity and security.

### Loading Data with Docker Compose

To load data into the knowledge base when using Docker Compose:

```bash
docker-compose -f docker/docker-compose.yaml exec nlweb python -m tools.db_load <url> <name>
```

For example:

```bash
docker-compose -f docker/docker-compose.yaml exec nlweb python -m tools.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
```

For development work, you can use the development container instead:

```bash
docker exec -it nlweb-dev python -m tools.db_load <url> <name>
```

## Loading Data with Docker

To load data into the knowledge base when using Docker directly:

```bash
docker exec -it <container_id> python -m tools.db_load <url> <name>
```

For example:

```bash
docker exec -it <container_id> python -m tools.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
```

## Accessing the Application

Once the container is running, you can access the application at:

```
http://localhost:8000
```

## Additional Information

For more detailed information about the NLWeb application, please refer to the main documentation in the repository.
