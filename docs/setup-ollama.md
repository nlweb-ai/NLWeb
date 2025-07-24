# Ollama

## Getting Started

Go to the [Ollama's](https://ollama.com/) website and install ollama for your machine.

## Prerequisites

Assumes you have [Ollama](https://ollama.com/) installed on your machine and you have the ollama server and the appropriate model running. 

## Setting up LLM

Go to `config/config_llm.yaml` file. At the top of the file select `ollama` as your `preferred_endpoint`

```
preferred_endpoint: ollama
...
```

Scroll down to the bottom, enter the model name you want to use on the high or on the low field depending on your setup.



Go to your `.env` file add your Ollama instance's url in the `OLLAMA_URL` field

## Setting up Embedding

Go to `config/config_embedding.yaml` file. At the top of the file select `ollama` as your `preferred_provider`
```
preferred_provider: ollama
.
.
.
```


Scroll down find the `ollama` section, enter your preferred model name that you want to use for embedding.

```
ollama:
    api_endpoint_env: OLLAMA_URL
    model: qwen3:0.6b
```