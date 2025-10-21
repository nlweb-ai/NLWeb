# NLWeb Docker Setup

This repository contains a [Dockerfile](../Dockerfile) for building and running the NLWeb application, which turns your website into an interactive chat application.

## Prerequisites & Configuration

Before building or running the Docker container, you need to configure the required environment variables and ensure your config files are set to call those resources.

### Required Environment Variables

For the application to function, you need at least one retrieval endpoint with credentials, and LLM credentials.  As an example, you could use the following:

- `AZURE_VECTOR_SEARCH_ENDPOINT`: Your Azure Vector Search endpoint
- `AZURE_VECTOR_SEARCH_API_KEY`: Your Azure Vector Search API key
- `OPENAI_API_KEY`: Your OpenAI API key

See the `.env.template` file in the code directory for all available configuration options.

### Variable Configuration Methods

There are two ways to configure these variables:

**Method 1: Using a `.env` file (recommended for local development):**

Create a `code/.env` file with your configuration:

```env
AZURE_VECTOR_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_VECTOR_SEARCH_API_KEY=your-api-key
OPENAI_API_KEY=your-openai-key
```

**Method 2: Environment variables (recommended for production):**

Export the variables in your shell or pass them directly to Docker commands:

```bash
export AZURE_VECTOR_SEARCH_ENDPOINT=https://your-search.search.windows.net
export AZURE_VECTOR_SEARCH_API_KEY=your-api-key
export OPENAI_API_KEY=your-openai-key
```

### Set Your Config Files

Update your config files (located in the config folder) to make sure your preferred providers match your .env file or environment variables so they are calling the correct resources. There are three files that may need changes.

- **config_llm.yaml**: Update the first line to the LLM provider you set in the .env file.  By default it is Azure OpenAI.  You can also adjust the models you call here by updating the models noted.  By default, we are assuming 4.1 and 4.1-mini.
- **config_embedding.yaml**: Update the first line to your preferred embedding provider.  By default it is Azure OpenAI, using text-embedding-3-small.
- **config_retrieval.yaml**: We will use qdrant_local for this exercise.  By default, this is set to write to qdrant_local and you can see the qdrant_local retrieval endpoint is enabled to 'true' in the following list of possible endpoints, as is Azure AI Search using the nlweb_west endpoint.  As you can see, you may have more than one retrival backend, but only one 'write' endpoint. You can see with the Azure AI search example how to add several databases of the same type.

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
docker run -it -p 8000:8000 \
  -v ./data:/data \
  -v ./code/config:/app/code/config:ro \
  -e AZURE_VECTOR_SEARCH_ENDPOINT=${AZURE_VECTOR_SEARCH_ENDPOINT} \
  -e AZURE_VECTOR_SEARCH_API_KEY=${AZURE_VECTOR_SEARCH_API_KEY} \
  -e OPENAI_API_KEY=${OPENAI_API_KEY} \
  nlweb:latest
```

### Using Docker Compose (Recommended)

This repository includes a [docker-compose.yaml](../docker-compose.yaml) file for easy deployment.

**To start the application:**

```bash
docker-compose up -d
```

**To stop the application:**

```bash
docker-compose down
```

The Docker Compose setup automatically uses environment variables from the `code/.env` file, so make sure your configuration is set up there first.

## Docker Image Details

The Docker image is built using a 2-stage build process to minimize the final image size:

- Stage 1: Installs all dependencies and build tools
- Stage 2: Creates the runtime environment with only the necessary components

### Platform Compatibility

When built using the multi-architecture build instructions, the Docker image can run on both:

- ARM64 architecture (e.g., Apple Silicon, AWS Graviton, Raspberry Pi)
- AMD64/x86_64 architecture (e.g., Intel, AMD)

This ensures that the image can be deployed on a wide range of hardware platforms without compatibility issues.

### Security Features

The Docker image includes several security features:

- System packages are updated to the latest versions during both build and runtime stages to address security vulnerabilities
- Minimal base image (python:3.10-slim) is used to reduce attack surface
- Non-root user is used to run the application
- Only necessary packages are installed with `--no-install-recommends` flag to minimize image size
- Package caches are cleaned up after installation to reduce image size

## Data Persistence & Volume Mounts

The Docker setup is configured with the following volume mounts:

1. **Data Directory**: Mounts the `./data` directory from your host to `/app/data` in the container. This allows data to persist between container restarts.

2. **Configuration Directory**: Mounts the `./config` directory from your host to `/app/config` in the container as read-only. This provides access to configuration files without allowing the container to modify them, ensuring configuration integrity and security.

## Loading Data

### Using Docker Compose

To load data into the your retrieval backend when using Docker Compose:

```bash
docker-compose exec nlweb python -m data_loading.db_load <url> <name>
```

For example:

```bash
docker-compose exec nlweb python -m data_loading.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
```

Note that the above will only work if you have set your 'write' endpoint as mentioned and provided an admin/write API key or enviornment variable. If your 'write' endpoint is set to a retrieval endpoint that is either not configured or has a read-only key, this will fail.

### Using Docker Run

### Using Docker Exec

To load data when using Docker directly:

```bash
docker exec -it <container_id> python -m data_loading.db_load <url> <name>
```

For example:

```bash
docker exec -it <container_id> python -m data_loading.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
```

## Accessing the Application

Once the container is running, you can access the application at:

```text
http://localhost:8000
```

## Additional Information

For more detailed information about the NLWeb application, please refer to the main documentation in the repository.
