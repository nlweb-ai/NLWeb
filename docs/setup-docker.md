# NLWeb Docker Image

This repository contains a [Dockerfile](../Dockerfile) for building and running the NLWeb application, which turns your website into a knowledge base.

## Docker Image

The Docker image is built using a 2-stage build process to minimize the final image size:
- Stage 1: Installs all dependencies and build tools
- Stage 2: Creates the runtime environment with only the necessary components

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

## Building the Docker Image

### Single Architecture Build

To build the Docker image for your current architecture:

```bash
docker build -t nlweb:latest .
```

### Multi-Architecture Build

To build the Docker image for multiple architectures (ARM64 and AMD64), you can use Docker's buildx feature:

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t nlweb:latest --push .
```

Note: The `--push` flag is required for multi-architecture builds. If you want to build without pushing to a registry, you can use the `--load` flag instead, but it only works for single-platform builds.

## Running the Docker Container

To run the Docker container:

```bash
docker run -p 8000:8000 -v ./config:/app/config:ro -v ./data:/data nlweb:latest
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

This repository includes a [docker-compose.yaml](../docker-compose.yaml) file for easy deployment of the NLWeb application.

### Running with Docker Compose

To start the application using Docker Compose:

```bash
docker-compose up -d
```

This will build the Docker image if it doesn't exist and start the container in detached mode.

To stop the application:

```bash
docker-compose down
```

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
docker-compose up -d
```

### Data Persistence with Docker Compose

The `docker-compose.yaml` file is configured with the following volume mounts:

1. **Data Directory**: Mounts the `./data` directory from your host to `/app/data` in the container. This allows data to persist between container restarts.

2. **Configuration Directory**: Mounts the `./config` directory from your host to `/app/config` in the container as read-only. This provides access to configuration files without allowing the container to modify them, ensuring configuration integrity and security.

### Loading Data with Docker Compose

To load data into the knowledge base when using Docker Compose:

```bash
docker-compose exec nlweb python -m data_loading.db_load <url> <name>
```

For example:

```bash
docker-compose exec nlweb python -m data_loading.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
```

## Loading Data with Docker

To load data into the knowledge base when using Docker directly:

```bash
docker exec -it <container_id> python -m data_loading.db_load <url> <name>
```

For example:

```bash
docker exec -it <container_id> python -m data_loading.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
```

## Accessing the Application

Once the container is running, you can access the application at:

```
http://localhost:8000
```

## Additional Information

For more detailed information about the NLWeb application, please refer to the main documentation in the repository.
