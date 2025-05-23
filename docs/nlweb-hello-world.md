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
    source myenv/bin/activate    # Or on Windows: myenv\Scripts\activate
    ```

3. Go to the 'code' folder in NLWeb to install the dependencies. Note that this will also install the local vector database requirements so you don't need to install them separately.

    ```sh
    cd code
    pip install -r requirements.txt
    ```

4. Copy the .env.template file to a new .env file and update the API key you will use for your LLM endpoint of choice. The local Qdrant database variables are already set for this exercise.  Don't worry; you do not need to provide all of these providers in the file.  We explain below.

    ```sh
    cp .env.template .env
    ```

5. Update your config files (located in the code/config folder) to make sure your preferred providers match your .env file. There are three files that may need changes.

    - config_llm.yaml: Update the first line to the LLM provider you set in the .env file.  By default it is Azure OpenAI.  You can also adjust the models you call here by updating the models noted.  By default, we are assuming 4.1 and 4.1-mini.
    - config_embedding.yaml: Update the first line to your preferred embedding provider.  By default it is Azure OpenAI, using text-embedding-3-small.
    - config_retrieval.yaml: Update this to qdrant_local for this exercise.  By default, this is Azure AI Search.

6. Now we will load some data in our local vector database to test with. We've listed a few RSS feeds you can choose from below. Note, you can also load all of these on top of each other to have multiple 'sites' to search across as well.  By default it will search all sites you load, but this is configured in config_nlweb.yaml if you want to scope your search to specific sites.

    The format of the command is as follows (make sure you are still in the 'code' folder when you run this):

    ```sh
    python -m tools.db_load <RSS URL> <site-name>
    ```

    Kevin's 'Behind the Tech' Podcast:

    ```sh
    python -m tools.db_load https://feeds.libsyn.com/121695/rss Behind-the-Tech
    ```

    Verge's 'Decoder' Podcast:

    ```sh
    python -m tools.db_load https://feeds.megaphone.fm/recodedecode Decoder
    ```

    You can find even more data, including other formats other than RSS, in this [OneDrive folder](https://1drv.ms/f/c/6c6197aa87f7f4c4/EsT094eql2EggGxlBAAAAAABajQiZ5unf_Ri_OWksR8eNg?e=I4z5vw). (Note:  If it asks you to login, try the URL a 2nd time. It should be open permissions.)

7. Start your NLWeb server (again from the 'code' folder):

    ```sh
    python app-file.py
    ```

8. Go to localhost:8000/

9. You should have a working search!  You can also try different sample UIs by adding 'static/<html file name>' to your localhost path above.
