# Database Load Tool Guide

## Getting Started

In the 'code/tools' folder, you will find 'db_load.py' tool. This tool allows you to:

- Compute embeddings and load the data into a vector database
- Remove files from an existing database
- Remove sites with associated files from an existing database

## Prerequisites

We assume you have already cloned the repo & setup your NLWeb environment, described in [nlweb-hello-world](./nlweb-hello-world.md), though you may be using different providers or database setup.  We'll discuss different options below.

Data must be in one of the following formats:
    1. Two columns per row, separated by tabs: URL and JSON
    2. One column: JSON only (URL will be extracted from the JSON)
    3. CSV file with headers
    4. RSS/Atom feed
    5. URL pointing to any of the above types

## Loading Data into a Vector Database

With this command, three things happen in the following order:

1. Point to an existing data source containing structured data (see above for supported data formats.) The tool will load/scrape the data.
2. The tool then computes the embeddings using your preferred embedding provider (configured in code/config_embedding.yaml)
3. The tool then loads the embeddings into the vector database (set in the code/config_retrieval.yaml file).  Note that if you are using a cloud service, such as Azure AI Search, you must have a key with write permissions to the database.

The command structure for this is as follows - run this while in your `myenv` virtual environment from the 'code' folder:

```sh
python -m tools.db_load <file-path> <site-name>
```

The 'file-path' can be a URL or local path.  The 'site-name' is what the data source is called if you want to scope your search (in code/config_nlweb.yaml) or need to remove the site and/or entries.

An example would look like:

```sh
python -m tools.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
```

## Removing Database Entries

Once you have loaded data, you might want to remove the database entries for a site without removing the site itself (e.g., if you have a site scope set in your config, but want to change the entries in the database).  To do this, use the following argument and again run from the 'code' folder:

```sh
python -m tools.db_load --only-delete delete-site <site-name>
```

For the example in our data load step, removing the entries would look like this:

```sh
python -m tools.db_load --only-delete delete-site Behind-the-Tech
```

<!-- ## Removing the Site and Database Entries

comment note: during testing, this said it required a path vs. site name. Line 1074 of db load doesn't match behavior in CLI

If you want to remove both the site and data associated with the site, you would use the following command, running from the 'code' folder:

```sh
python -m tools.db_load --delete-site <site-name>
```

Again, for the example in our data load step, removing the entire site and data would look like:

```sh
python -m tools.db_load --delete-site Behind-the-Tech
```
-->

## Optional Arguments

- **Using a different database than set in your config:**  Append `--database <preferred endpoint>' Here, 'preferred endpoint' refers to the database set in code/config_retrieval.yaml. For example, if you had your preferred endpoint sent to 'qdrant-local', you could override this and write to another configured (but not preferred) retrieval provider like 'azure-ai-search' with the following:

```sh
python -m tools.db_load <https://feeds.libsyn.com/121695/rss> Behind-the-Tech --database azure-ai-search
```

- **Many URLs to load:**  A faster method in this case is to make a list of these URLs in a file to do batch processing into a single site.  For example, if you had 10 RSS feeds you wanted to load, you could create a .txt file with 1 URL per line. Append '--url-list' to the command to do this.

```sh
python -m tools.db_load /some-folder/my-podcast-list.txt Podcast-List --url-list
```

- **Change the batch size:**  You might notice when loading data, that it gets by default batched into groups of 100.  If you would like to change the batch size to a different number of items, you append '--batch-size <batch size>' to the command. The below example would change the batch size to 200 instead of the default of 100.

```sh
python -m tools.db_load /some-folder/my-podcast-list.txt Podcast-List --url-list --batch-size 200
```

<!--
```sh
--force-recompute - we need an example use case
```
-->
