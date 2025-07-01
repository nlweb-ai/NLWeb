# Configuration files

The NLWeb implementation in this repo supports a number of different vector stores, LLMs and embedding providers. The directory called config contains all the configurations.

We have the following configuration files (all yaml):

- `llm` : specifies the available llms and the environment variables in which their endpoint, API keys etc. can be found. These might need to be appropriately modified. The top line <code>preferred_provider</code> specifies which llm should be used as the default. Some of the llm calls require slightly better models and some like the ranking calls prefer lighter models. This is specified using the high and low parameters

- `embedding`: similar to llms, specifies providers, endpoints, etc. Note that the embedding is integral to retrieval and the same embedding needs to be used for creating the vector store and retrieving from it.

- `retrieval`: specifies the available vector stores. As above variables specify endpoint, API keys, etc. At this point, only one of the stores is queried. In future, we will query all the available stores. We do not assume that the backend is a vector store. We are in the process of adding Restful vector stores, which will enable one NLWeb instance to treat another as its backend.
    - We do assume that the vector store will return a list of the database items encoded as json objects, preferably in a schema.org schema.

- `nlweb`: specifies the location of the json file that may be used for data uploads. Also species the prompt to be used with chatbots when communicating with them over MCP

- `webserver`: most of the variables are self explanatory. The server can be run in development or production mode. When in development mode, query parameters can override what is in the config for retrieval and llm
