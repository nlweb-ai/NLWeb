# Cloudflare AutoRAG

Cloudflare AutoRAG is a service that allows you to build Retrieval-Augmented Generation (RAG) applications using your data, stored on Cloudflare's platform. This guide will help you set up and connect to your Cloudflare AutoRAG instance for use within NLWeb-powered applications.

## Prerequisites

- A Cloudflare account. You can create one at https://www.cloudflare.com/sign-up.
- An existing AutoRAG instance or the ability to create one. See https://developers.cloudflare.com/autorag/ for further details.
- An API token with permissions to access the AutoRAG service. See https://developers.cloudflare.com/fundamentals/api/get-started/create-token/

## Use Cloudflare AutoRAG for retrieval

Edit [config_retrieval.yaml](../code/config_retrieval.yaml) and change `write_endpoint` at the top to `write_endpoint: cloudflare_autorag`. Then, in your `.env` file, set the following variables:

* `CLOUDFLARE_API_TOKEN`: Your Cloudflare Account API key. You can generate this token in the Cloudflare dashboard under "Profile" -> "API Tokens". 
* `CLOUDFLARE_RAG_ID_ENV`: The ID of your AutoRAG instance. This is the name of the AutoRAG as it appears in the Cloudflare dashboard.
* `CLOUDFLARE_ACCOUNT_ID`: Your Cloudflare Account ID. See [this page](https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/) to find your Account ID.

## Test connectivity

Run from 'python' directory:

```sh
python code/python/testing/check_connectivity.py
```

You'll see a three line report on configuration whether configuration has been set correctly for your selected Cloudflare AutoRAG instance.