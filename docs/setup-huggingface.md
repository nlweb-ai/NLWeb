# Hugging Face Inference Providers

Hugging Face offers an easy and unified access to serverless AI inference through multiple inference providers, like [Together AI](https://together.ai/), [Cerebras](https://www.cerebras.ai/) and [Fireworks AI](https://fireworks.ai/). More details in the [Inference Providers documentation](https://huggingface.co/docs/inference-providers/index).

You can check available models for an inference provider by going to [huggingface.co/models](https://huggingface.co/models), clicking the "Other" filter tab, and selecting your desired provider. For example, you can find all Fireworks AI supported models [here](https://huggingface.co/models?inference_provider=fireworks-ai&sort=trending).

**Important Note**: The provider is set to "auto" in NLWeb, which will select the first of the providers available for the model, sorted by the user's order in https://hf.co/settings/inference-providers.

## Billing & Authentication

Billing is centralized on your Hugging Face account, no matter which providers you are using. You are billed the standard provider API rates with no additional markup - Hugging Face simply passes through the provider costs. Note that [Hugging Face PRO](https://huggingface.co/subscribe/pro) users get $2 worth of Inference credits every month that can be used across providers.

With a single Hugging Face token, you can access inference through multiple providers. Your calls are routed through Hugging Face and the usage is billed directly to your Hugging Face account at the standard provider API rates.
Simply set the `HF_TOKEN` environment variable with your Hugging Face token, you can create one here: https://huggingface.co/settings/tokens.



