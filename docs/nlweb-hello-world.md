# NLWeb Hello World

## Getting Started

Getting your NLWeb Server up and running locally.

This will get you up and running, using a local vector database and RSS feeds we have provided some links to below. You can replace this later with your own database.

## Prerequisites

These instructions assume that you have Python 3.10+ installed locally.

## From the Terminal

1. Clone or download the code from the repo.

    ```sh
    git clone https://github.com/microsoft/NLWeb
    cd NLWeb
    ```

2. Open a terminal to create a virtual python environment and activate it.

    ```sh
    python -m venv myenv
    source myenv/bin/activate
    ```

    On Windows (cmd.exe or PowerShell):

    ```cmd
    myenv\Scripts\activate
    ```

3. Go to the 'AskAgent/python' folder in NLWeb to install the dependencies. Note that this will also install the local vector database requirements used later in this example so you don't need to install them separately.

    ```sh
    cd AskAgent/python
    pip install -r requirements.txt
    ```

4. Copy the .env.template file to a new .env file under the main folder and update the API key you will use for your LLM endpoint of choice. The local Qdrant database variables are already set for this exercise.  Don't worry; you do not need to provide all of these providers in the file.  We explain below.

    ```sh
    cd ../../
    cp .env.template .env
    ```

    On Windows (cmd.exe):

    ```cmd
    copy .env.template .env
    ```

5. Update your config files (located in the config folder) to make sure your preferred providers match your .env file. There are three files that may need changes.

    - config_llm.yaml: Update the `preferred_endpoint` (first line) to the LLM provider you set in the .env file. By default it is `azure_openai`. If you are using OpenAI directly, change it to `openai`. You can also adjust the models listed under each provider. The default OpenAI models are gpt-4.1 and gpt-4.1-mini.
    - config_embedding.yaml: Update the `preferred_provider` (first line) to your preferred embedding provider. By default it is `azure_openai`. If you are using OpenAI directly, change it to `openai`. The default embedding model is text-embedding-3-small.
    - config_retrieval.yaml: We will use `qdrant_local` for this exercise. By default, the `write_endpoint` is set to `qdrant_local`. You will see several retrieval endpoints listed — for a simple local setup, make sure `qdrant_local` is set to `enabled: true` and set any other endpoints you don't have credentials for to `enabled: false` (e.g., `nlweb_west`, `shopify`). You can have more than one retrieval backend enabled, but only one `write_endpoint`.

6. You can verify that your configuration is set properly and you remembered to set all needed API keys by running the check-connectivity script from the python directory.  There is more information [here](nlweb-check-connectivity.md).

    ```sh
    cd AskAgent/python
    python testing/check_connectivity.py
    ```

7. Now we will load some data in our local vector database to test with. We've listed a few RSS feeds you can choose from below. Note, you can also load all of these on top of each other to have multiple 'sites' to search across as well.  By default it will search all sites you load, but this is configured in config_nlweb.yaml if you want to scope your search to specific sites.

    The format of the command is as follows (make sure you are still in the 'python' folder when you run this):

    ```sh
    # Run from AskAgent/python folder
    python -m data_loading.db_load <RSS URL> <site-name>
    ```

    Vox's 'Today, Explained' Podcast:

    ```sh
    python -m data_loading.db_load https://feeds.megaphone.fm/VMP5705694065 Today-Explained
    ```

    BBC's 'Test Match Special' Cricket Podcast:

    ```sh
    python -m data_loading.db_load https://podcasts.files.bbci.co.uk/p02nrsl2.rss TMS-Cricket
    ```

    More cricket podcasts you can add:

    ```sh
    # BBC Stumped — weekly global cricket podcast
    python -m data_loading.db_load https://podcasts.files.bbci.co.uk/p02gsrmh.rss Stumped-Cricket

    # The Final Word — match analysis with Geoff Lemon and Adam Collins
    python -m data_loading.db_load https://audioboom.com/channels/4936611.rss Final-Word-Cricket
    ```

    You can find even more data, including other formats other than RSS, in this [OneDrive folder](https://1drv.ms/f/c/6c6197aa87f7f4c4/EsT094eql2EggGxlBAAAAAABajQiZ5unf_Ri_OWksR8eNg?e=I4z5vw). (Note:  If it asks you to login, try the URL a 2nd time. It should be open permissions.)

8. Start your NLWeb server (again from the 'AskAgent/python' folder):

    ```sh
    # Run from AskAgent/python folder
    python app-aiohttp.py
    ```

9. Go to http://localhost:8000/

10. You should have a working search!  You can also try different sample UIs by adding 'static/\<html file name>' to your localhost path above.
