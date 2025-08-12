# Demos

[Import data from an RSS feed](#import-data-from-an-rss-feed)

[Agent-enable your Github data](#agent-enable-your-github-data)

[Ask questions of clinical trial data](#ask-questions-of-clinical-trial-data)

## Import data from an RSS feed
With NLWeb, you can easily import data from an RSS feed for querying over in natural language using a script.  

First, navigate to the NLWeb --> code --> python directory.  Before you run this command, ensure that the database you want to write to is set as the `preferred_endpoint` in your config_retrieval.yaml file in the config directory (or use the --database switch). In this example, I am using qdrant_local.  

The format for this command is the following.  Replace with an RSS feed, and choose a descriptive site name for that data.   
```sh
# Run from the code/python folder
python -m data_loading.db_load <rss feed link> <site name> 
```

As an example, here is the RSS feed for Kevin Scott's podcast "Behind the Tech".  This command will extract the data from the RSS feed, create embeddings, and store those embeddings in the vector database specified in the config_retrieval.yaml file.  
```sh
# Run from the code/python folder
python -m data_loading.db_load https://feeds.libsyn.com/121695/rss behindthetech
```

Now, using our debug tool, you can easily ask questions about your Github data in natural language.  Start your web server by running `python app-file.py` from the **code/python** directory.  Then in a web browser, navigate to http://localhost:8000/static/str_chat.html.  Select "behindthetech" from the site dropdown and your retrieval provider from the database dropdown (I am using "Qdrant Local").  Then ask questions in natural language.  

!["Screenshot showing a chat interface with a question 'Has Kevin had any guests that are book authors?' and a list of podcast authors returned"](img/bookauthors.jpg)

If you have created a new site name, you will need to add this to the list of site options in the dropdown-interface.js file in the static directory for it to appear in the tool above.  

NOTE: to remove the "behindthetech" data from your vector database, run this:
```sh
# Run from the code/python folder
python -m data_loading.db_load --only-delete delete-site behindthetech
```


## Agent-enable your Github data
Let's create an agent that utilizes NLWeb over GitHub data.  

First, follow these instructions to get a fine-grained personal access token from GitHub: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token 

Copy the .env.example file into a new file called .env.  In the .env file, update the value of GITHUB_TOKEN to the value of the token you generated.  

First, we will run a script to get your Github data into a format that NLWeb can consume.  It will output a json file.  From the **demo** folder, run:
```sh
# Run from the demo folder
python extract_github_data.py
```

Then, you can extract this data, create embeddings, and import them into your retrieval provider with this script.  From the **code/python** folder, run the db_load tool, pointing to the json file that you just created and giving it a site name like "github":
```sh
# Run from the code/python folder
python -m data_loading.db_load ../../demo/ghrepoinfo.json github
```

Finally, you can repeat the same process as above.  Start the web server with the below command.
```sh
python app-file.py
```

Then in a web browser, navigate to http://localhost:8000/static/str_chat.html.  You can now ask questions of your data. 

!["Screenshot showing a chat interface with a question 'What repos have the MIT license?' and a list of code repositories returned"](img/github.jpg)


## Ask questions of clinical trial data
In this demonstration, we will import data on clinical trials that is available on the website https://clinicaltrials.gov.  

First, search the website and download the latest clinical trial data on any topic.  For example, you can search for "cancer" with this query: https://clinicaltrials.gov/expert-search?term=Cancer 

Then, on the search results page, click the "Download" button.  This will present a screen like the following.  Choose to download JSON (and check the box to put each study into a separate file and download them as a zip archive), the number of results you would like, and all available data fields.  

![Download Options](img/download-options.png)

If you encounter any issues, there is more information on how to download the clinical trial data at https://clinicaltrials.gov/data-api/how-download-study-records.  

Once you have downloaded the zip file, extract all files from the zip into a directory and note the name of that directory.  In the sample code, we have downloaded to `C:\Data\ctg-studies`.  

In the demo folder, open the file called `import_clinical_trials.py` and set the `json_dir` variable near the top to the value of the directory where your extracted json files are.  

Now, we will run two commands to process the data.  These commands should be run from the "code/python" directory.  In the second command, replace 'C:\Data\ctg-studies' with the value of the directory where you extracted the files (**but note that 'processed' should remain appended to the end**).  

```
python ..\..\demo\import_clinical_trials.py
python -m data_loading.db_load C:\Data\ctg-studies\processed\ CancerClinicalTrials --directory
```

Finally, you can query the data that you have imported.  Still in the code/python directory, start the service by running:

```
python app-file.py
```

Open a web browser and navigate to http://localhost:8000/static/fp_chat.html.  You should be able to ask questions of this data.  

![Cancer Questions](img/cancerquestions.jpg)
