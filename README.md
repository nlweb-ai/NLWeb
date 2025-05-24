# What is NLWeb ?

**NLWeb** simplifies the process of building conversational interfaces for websites. It natively supports MCP (Model Context Protocol), allowing the same natural language APIs to serve both humans and AI agents.

Schema.org and related semi-structured formats like RSS — used by over 100 million websites — have become not just de facto syndication mechanisms, but also a semantic layer for the web. NLWeb leverages these to enable natural language interfaces more easily.

NLWeb is a collection of open protocols and associated open source tools. Its main focus is establishing a foundational layer for the AI Web — much like HTML revolutionized document sharing. To make this vision reality, NLWeb provides practical implementation code—not as the definitive solution, but as proof-of-concept demonstrations showing one possible approach. We expect and encourage the community to develop diverse, innovative implementations that surpass our examples. This mirrors the web's own evolution, from the humble 'htdocs' folder in NCSA's http server to today's massive data center infrastructures—all unified by shared protocols that enable seamless communication.

AI has the potential to enhance every web interaction. Realizing this requires a collaborative spirit reminiscent of the Web's early "barn raising" days. Shared protocols, sample implementations, and community participation are all essential. NLWeb brings together protocols, Schema.org formats, and sample code to help sites quickly implement conversational endpoints — benefitting both users through natural interfaces and agents through structured interaction.

> Join us in building this connected web of agents.

## How It Works

NLWeb has two primary components:

1. **A simple protocol** to interact with a site using natural language. It returns responses in JSON using Schema.org. See [REST API docs](/docs/nlweb-rest-api.md) for details.

2. **A straightforward implementation** that uses existing markup on sites with structured lists (e.g., products, recipes, attractions, reviews). Combined with UI widgets, this enables conversational interfaces to be added with ease. See [Life of a Chat Query](docs/life-of-a-chat-query.md) for more details.

## NLWeb and MCP

MCP (Model Context Protocol) is an emerging standard for enabling chatbots and AI assistants to interact with tools. Every NLWeb instance also acts as an MCP server and supports a core method, `ask`, which allows a natural language question to be posed to a website.

The response returned uses Schema.org — a widely adopted vocabulary for describing web data.

**In short, MCP is to NLWeb what HTTP is to HTML.**

## Platform Compatibility

NLWeb is platform-agnostic and supports:

* **Operating systems**: Windows, macOS, Linux
* **Vector stores**: Qdrant, Snowflake, Milvus, Azure AI Search
* **LLMs**: OpenAI, DeepSeek, Gemini, Anthropic, Inception

It is designed to be lightweight and scalable — capable of running on everything from data center clusters to laptops and, soon, mobile devices.

## Repository

This repository includes:

* Core service code for handling natural language queries
* Connectors for popular LLMs and vector databases
* Tools to ingest data (e.g., Schema.org JSONL, RSS) into a vector database
* A web server front end that includes the service and a sample UI

Most production deployments will:

* Use their own user interface
* Integrate NLWeb directly into their application environment
* Connect NLWeb to live databases instead of duplicating content (to avoid freshness issues)

## Documentation

### Getting Started

* [Hello World on Your Laptop](docs/nlweb-hello-world.md)
* [Running on Azure](docs/setup-azure.md)
* Running on GCP — *coming soon*
* Running on AWS — *coming soon*

### NLWeb Details

* [Life of a Chat Query](docs/life-of-a-chat-query.md)
* [Modifying Prompts](docs/nlweb-prompts.md)
* [Changing Control Flow](docs/nlweb-control-flow.md)
* [Modifying the User Interface](docs/user-interface.md)
* [REST API](docs/nlweb-rest-api.md)
* [Adding Memory](docs/nlweb-memory.md)

## License

NLWeb uses the [MIT License](LICENSE).

## Deployment (CI/CD)

CI/CD pipelines are not yet included. Contributions to add automated testing or deployment workflows are welcome.

## Access

For questions about this GitHub project, please contact [NLWeb Support](mailto:NLWebSup@microsoft.com).

## Contributing

See [Contribution Guidance](CONTRIBUTING.md) for more details.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
