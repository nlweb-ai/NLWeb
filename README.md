# What is NLWeb?

**NLWeb** simplifies the process of building conversational interfaces for websites. It natively supports MCP (Model Context Protocol), allowing the same natural language APIs to serve both humans and AI agents.

Schema.org and related semi-structured formats like RSS — used by over 100 million websites — have become not just de facto syndication mechanisms, but also a semantic layer for the web. NLWeb leverages these to enable natural language interfaces more easily.

NLWeb is a collection of open protocols and associated open source tools. Its main focus is establishing a foundational layer for the AI Web — much like HTML revolutionized document sharing. To make this vision reality, NLWeb provides practical implementation code—not as the definitive solution, but as proof-of-concept demonstrations showing one possible approach. We expect and encourage the community to develop diverse, innovative implementations that surpass our examples. This mirrors the web's own evolution, from the humble 'htdocs' folder in NCSA's http server to today's massive data center infrastructures—all unified by shared protocols that enable seamless communication.

AI has the potential to enhance every web interaction. Realizing this requires a collaborative spirit reminiscent of the Web's early "barn raising" days. Shared protocols, sample implementations, and community participation are all essential. NLWeb brings together protocols, Schema.org formats, and sample code to help sites quickly implement conversational endpoints — benefitting both users through natural interfaces and agents through structured interaction.

Join us in building this connected web of agents.

## How It Works

NLWeb has two primary components:

1. **A simple protocol** to interact with a site using natural language. It returns responses in JSON using Schema.org. See the [NLWeb spec](https://nlweb.ai/spec) for details.

2. **A straightforward implementation** that uses existing markup on sites with structured lists (e.g., products, recipes, attractions, reviews). Combined with UI widgets, this enables conversational interfaces to be added with ease.

## NLWeb and MCP/A2A

MCP and A2A are emerging standards for enabling chatbots and AI assistants to interact with tools and each other. Every NLWeb instance also acts as an MCP server (and soon A2A) and supports a core method, `ask`, which allows a natural language question to be posed to a website.

The response returned uses Schema.org — a widely adopted vocabulary for describing web data.

**In short, NLWeb is to MCP/A2A what HTML is to HTTP.**

## Platform Compatibility

NLWeb is platform-agnostic and supports:

* **Operating systems**: Windows, macOS, Linux
* **Vector stores**: [Qdrant](docs/setup-qdrant.md), [Snowflake](docs/setup-snowflake.md), [Milvus](docs/setup-milvus.md), [Azure AI Search](docs/setup-azure.md), [Elasticsearch](docs/setup-elasticsearch.md), [Postgres](docs/setup-postgres.md), [Cloudflare AutoRAG](docs/setup-cloudflare-autorag.md)
* **LLMs**: OpenAI, DeepSeek, Gemini, Anthropic, Inception, [HuggingFace](docs/setup-huggingface.md)

It is designed to be lightweight and scalable — capable of running on everything from data center clusters to laptops and, soon, mobile devices.

## Repository Structure

This repository is organized into the following modules:

* **[AskAgent](AskAgent/)** — The core NLWeb query agent. Handles natural language queries against websites using Schema.org structured data, with connectors for popular LLMs and vector databases, data ingestion tools, and a sample web UI.
* **[AgentFinder](AgentFinder/)** — Agent discovery service for finding and routing to NLWeb agents across the web.
* **[DataFinder](DataFinder/)** — Natural language to SQL translator for enterprise data sources (HubSpot, Dynamics 365, Jira) using schema.org-based ontology mappings.
* **[ModelRouter](ModelRouter/)** — LLM model routing and scoring, selecting cost-effective models that meet quality thresholds.
* **[NLWebScorer](NLWebScorer/)** — Neural scorer models for ranking and evaluating search result quality.

Supporting directories:

* **[config](config/)** — YAML configuration files for LLM providers, embedding models, retrieval backends, and web server settings.
* **[static](static/)** — Frontend web UI assets (HTML, CSS, JavaScript) served by the web server.
* **[demo](demo/)** — Demo scripts and example data sources for getting started.
* **[scripts](scripts/)** — CLI utilities and helper scripts.
* **[docs](docs/)** — Full documentation.

Most production deployments will:

* Use their own user interface
* Integrate NLWeb directly into their application environment
* Connect NLWeb to live databases instead of duplicating content (to avoid freshness issues)

## Documentation

### Getting Started

* [Hello world on your laptop](docs/nlweb-hello-world.md)
* [Running it on Azure](docs/setup-azure.md)
* Running on GCP — *coming soon*
* Running on AWS — *coming soon*

### NLWeb Details

* [Modifying Prompts](docs/nlweb-prompts.md)
* [Changing Control Flow](docs/nlweb-control-flow.md)
* [Modifying the User Interface](docs/nlweb-user-interface.md)
* [REST API](docs/nlweb-rest-api.md)
* [Adding Memory](docs/nlweb-memory.md)
* [Using the Check Connectivity Script to Test your Configuration](docs/nlweb-check-connectivity.md)

## License

NLWeb uses the [MIT License](LICENSE).

## Deployment (CI/CD)

CI/CD pipelines are not yet included. Contributions to add automated testing or deployment workflows are welcome.

## Access

For questions about this GitHub project, please contact [NLWeb Support](mailto:NLWebSup@microsoft.com).

## Contributing

See [Contribution Guidance](CONTRIBUTING.md) for more details.

## Contributor Wall of Fame

[![nlweb contributors](https://contrib.rocks/image?repo=microsoft/nlweb)](https://github.com/microsoft/nlweb/graphs/contributors)

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
