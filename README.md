# What is NLWeb

Building conversational interfaces for websites is hard. NLWeb seeks to make it easy for websites to do this. And since NLWeb natively speaks MCP, the same natural language APIs can be used both by humans and agents.

Schema.org and related semi-structured formats like RSS, in use by over 100m websites, have become not just the defacto syndication mechanism but also the semantic layer for the web. NLWeb leverages these to make it much easier to create natural language interfaces.

NLWeb is a collection of open protocols and associated open source tools. Its main focus is establishing a foundational layer for the AI Web — much like HTML revolutionized document sharing. To make this vision reality, NLWeb provides practical implementation code—not as the definitive solution, but as proof-of-concept demonstrations showing one possible approach. We expect and encourage the community to develop diverse, innovative implementations that surpass our examples. This mirrors the web's own evolution, from the humble 'htdocs' folder in NCSA's http server to today's massive data center infrastructures—all unified by shared protocols that enable seamless communication.

AI has the potential to enhance every web interaction, but realizing this vision requires a collaborative effort reminiscent of the Web's early "barn raising" spirit. Success demands shared protocols, sample implementations, and community participation. NLWeb combines protocols, Schema.org formats, and sample code to help sites rapidly create these endpoints, benefiting both humans through conversational interfaces and machines through natural agent-to-agent interaction.

> Join us in building this connected web of agents.

## How it Works

 There are two distinct components to NLWeb.

 1. A protocol, very simple to begin with, to interface with a site in natural
     language and a format, leveraging json and schema.org for the returned answer.
     See the documentation on the [REST API](/docs/nlweb-rest-api.md) for more details.

 2. A straightforward implementation of (1) that leverages existing markup, for
      sites that can be abstracted as lists of items (products, recipes, attractions,
      reviews, etc.). Together with a set of user interface widgets, sites can
      easily provide conversational interfaces to their content. See the documentation
      on [Life of a chat query](docs/life-of-a-chat-query.md) for more details on how this works.

## NLWeb and MCP

 MCP (Model Context Protocol) is an emerging protocol for Chatbots and AI assistants
 to interact with tools. Every NLWeb instance is also an MCP server, which supports one core method,
 <code>ask</code>, which is used to ask a website a question in natural language. The returned response
 leverages schema.org, a widely-used vocabulary for describing web data. In short, MCP is to NLWeb what HTTP is to HTML.

## NLWeb and platforms

NLWeb is deeply agnostic:

- About the platform: We have tested it running on Windows, MacOS, Linux...
- About the vector stores used: Qdrant, Snowflake, Milvus, Azure AI Search...
- About the LLM: OAI, Deepseek, Gemini, Anthropic, Inception...
- It is intended to be both lightweight and scalable, running on everything from clusters
  in the cloud to laptops and soon phones.

## Repository

This repository contains the following:

- The code for the core service -- handling a natural language query on how this can be extended / customized.
- Connectors to some of the popular LLMs and vector databases.
- Tools for adding data in schema.org jsonl, RSS, etc. to a vector database of choice.
- A web server front end for this service. The service, being small enough runs in the web server.
- A simple UI for enabling users to issue queries via this web server.

We expect most production deployments to use their own UI. They are also likely to integrate the code into their application environment (as opposed to running a standalone NLWeb server). They are also encouraged to connect NLWeb to their 'live' database as opposed to copying the contents over, which inevitably introduces freshness issues.

## Documentation

### Getting Started

- [Hello world on your laptop](docs/nlweb-hello-world.md)
- [Running it on Azure](docs/setup-azure.md)
- Running it on GCP... coming soon
- Running it AWS... coming soon

### NLWeb

- [Life of a Chat Query](docs/life-of-a-chat-query.md)
- [Modifying behaviour by changing prompts](docs/nlweb-prompts.md)
- [Modifying control flow](docs/nlweb-control-flow.md)
- [Modifying the user interface](/docs/user-interface.md)
- [REST interface](docs/nlweb-rest-api.md)
- [Adding memory to your NLWeb interface](/docs/nlweb-memory.md)

---

### License

NLWeb uses the [MIT License](LICENSE).

### Deployment (CI/CD)

_At this time, the repository does not use continuous integration or produce a website, artifact, or anything deployed._

### Access

For questions about this GitHub project, please reach out to [NLWeb Support](mailto:NLWebSup@microsoft.com).

### Contributing

Please see [Contribution Guidance](CONTRIBUTING.md) for more information.

### Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
