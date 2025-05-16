# NL Web Configuration and CLI Guide

## Introduction

NL Web provides a command-line interface (CLI) to simplify configuration, testing, and execution of the application. The CLI helps users navigate through the various configuration steps, ensuring all necessary environment variables and settings are properly set up before running the application.

## Getting Started

To set up the `nlweb` command-line interface, you need to source the setup script first:

```bash
source setup.sh
```

This will temporarily add the `nlweb` command to your PATH and create an alias for easier use. 

### The NL Web CLI offers several advantages:

1. **Simplified Configuration**: The CLI guides users through selecting and configuring LLM providers and retrieval endpoints, automatically detecting which environment variables need to be set.

2. **Preference Management**: The CLI remembers user preferences, such as preferred LLM provider and retrieval endpoint, storing them in configuration files for future use.

3. **Environment Validation**: Before running the main application, the CLI can check connections to Azure OpenAI, Snowflake, or other services, ensuring everything is properly configured.

4. **Interactive Setup**: Rather than requiring users to manually edit configuration files, the CLI provides an interactive process to select options and input necessary credentials.

5. **Consistent Environment**: The CLI ensures that all required environment variables are properly set and persisted in the `.env` file.

## CLI Commands

The `nlweb` CLI provides the following commands:

| Command | Description |
|---------|-------------|
| `init`  | Configure the LLM provider and retrieval endpoint |
| `check` | Verify connectivity for selected configuration and environment variables |
| `app`   | Run the web application |
| `run`   | End-to-end flow: Runs `init`, `check`, and `app` sequentially |

### Common Flags

| Flag | Description |
|------|-------------|
| `-h`, `--help` | Display help information |
| `-d`, `--debug` | Enable debug output for troubleshooting |

## Usage Examples

### Complete Workflow

For a complete end-to-end workflow that configures, tests, and runs the application:

```bash
nlweb run
```

### Configuration Setup

To configure your environment:

```bash
nlweb init
```

This will guide you through selecting an LLM provider (e.g., Azure OpenAI, OpenAI, Anthropic, etc.) and a retrieval endpoint (e.g., Azure Vector Search, Qdrant, Snowflake Cortex, etc.). The CLI will then prompt you for any required API keys or endpoints.

### Connection Test

To verify your configuration can connect to the required services:

```bash
nlweb check
```

This runs connectivity tests to ensure your environment variables are correctly set and that the application can communicate with the selected services.

### Running the Application

To start the web application:

```bash
nlweb app
```


## Configuration Files

The CLI manages several YAML configuration files:

- `code/config/config_llm.yaml`: LLM provider configuration
- `code/config/config_retrieval.yaml`: Retrieval endpoint configuration

These files store settings including:
- Preferred providers/endpoints
- Model names and configurations
- Environment variable names for API keys and endpoints

## Environment Variables

The CLI helps manage environment variables required by the application, storing them in `.env`. These typically include:

- API keys for various LLM providers (OpenAI, Azure OpenAI, Anthropic, etc.)
- Endpoints for services (Azure Vector Search, Qdrant, etc.)
- Other configuration options specific to each provider or endpoint

### Pre-Existing Environment Variables

If an environment variable is already set in your shell, the CLI will use that value and won't prompt you to enter it again. This is useful when:

- You have environment variables set in your shell profile
- You're using a CI/CD pipeline with pre-configured secrets
- You want to script the configuration process

For example, if you've already set `AZURE_OPENAI_API_KEY` in your terminal session:

```bash
export AZURE_OPENAI_API_KEY="your-api-key-here"
nlweb init
```

The CLI will detect this value and skip prompting for it during the setup process.

## Advanced Usage

### Switching Providers or Endpoints

You can switch between different LLM providers or retrieval endpoints at any time by running:

```bash
nlweb init
```

The CLI will update your preference in the configuration files and prompt for any additional required environment variables.

### Debugging

When experiencing issues, run commands with the debug flag:

```bash
nlweb run -d
```

This provides detailed logging information that can help identify configuration problems.

## Conclusion

The NL Web CLI simplifies the process of configuring, testing, and running the application, ensuring all necessary services are properly connected and environment variables are set. This allows users to focus on using the application rather than dealing with complex setup procedures.