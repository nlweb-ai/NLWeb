# Responsible AI FAQ

## What is NLWeb?

NLWeb, or ‘Natural Language Web,’ allows users to easily add natural language search to their websites. It leverages existing site schema data stored in a vectorized database, eliminating the need for advanced AI skills to implement.  This repo contains one possible 'default' implementation that can fit many search scenarios, using Azure components - however, both the code and components are flexible and may be altered as desired based on the website environment and scenario needs.

## What can NLWeb do?

When a site uses NLWeb, the end-user is able to query the site to search in natural language and return relevant items, which you know exist because the results are returned from the database (e.g., they are not LLM generated results). Traditional keyword search is unable to understand the complex and potentially multi-turn queries for which NLWeb is able to quickly return relevant results and have a conversation with you in order to refine them.

## What is NLWeb’s intended use(s)?

NLWeb is intended to be used as a search mechanism across structured data for use on a webpage.  While the default implementation assumes we are using schema.org data and returning results to a website, this is not required and customers could instead use, for example, their content catalog or some other structured data stored as embeddings in a vector database, and return results in an application using search.  This is a matter of customizing the 'default' code provided.  We recommend that users note on their sites when using generative content that generative content may be inaccurate.

We strongly encourage users to use LLMs/MLLMs that support robust Responsible AI mitigations, such as Azure Open AI (AOAI) services. Such services continually update their safety and RAI mitigations with the latest industry standards for responsible use. For more on AOAI’s best practices when employing foundations models for scripts and applications:

- [Overview of Responsible AI practices for Azure OpenAI models](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/overview)
- [Azure OpenAI Transparency Note](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/transparency-note)
- [Azure OpenAI’s Code of Conduct](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/code-of-conduct)

## How was NLWeb evaluated? What metrics are used to measure performance?

NLWeb was evaluated with a variety of prompts and techniques.

- Transparency and groundedness of responses is tested via human inspection of the underlying context returned.
- We test both user prompt injection attacks (“jailbreaks”) and cross prompt injection attacks (“data attacks”) using manual and semi-automated techniques.
- Hallucinations are evaluated using adversarial attacks to attempt a forced hallucination through adversarial and exceptionally challenging datasets.

## What are the limitations of NLWeb? How can users minimize the impact of NLWeb’s limitations when using the system?

NLWeb requires structured data to search across, with this default implementation assuming a web schema in a vector database.  Initial queries are deliberatively generic and allow for common search patterns.  However, there are a few prompts containing specific examples of ways to make prompts more domain specific if there are particular search aspects the site wishes to emphasize/consider for their end-users.

## What operational factors and settings allow for effective and responsible use of NLWeb?

While NLWeb has been evaluated for its resilience to prompt and data corpus injection attacks, and has been probed for specific types of harms, the LLM that the user calls with NLWeb may produce inappropriate or offensive content, which may make it inappropriate to deploy for sensitive contexts without additional mitigations that are specific to the use case and model. Developers should assess outputs for their context and use available safety classifiers, model specific safety filters and features (such as [Azure AI Content Safety](https://azure.microsoft.com/en-us/products/ai-services/ai-content-safety)), or custom solutions appropriate for their use case.
