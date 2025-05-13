# NLWeb

Add LLM chat functionality to your existing web pages by leveraging your site schema

-----------------------------------------------------------------

## License 

NLWeb uses the [MIT License](LICENSE).


## Getting Started

Use these instructions to run an NLWeb server - below we have instructions for:
- [Running an NLWeb service locally](#local-setup)
- [Azure OpenAI endpoint creation instructions](#azure-openai-endpoint-creation)
- [Deploying NLWeb to a WebApp Service](#deploying-nlweb-to-an-azure-webapp)

## Prerequisites

These instructions assume that you have an [Azure subscription](https://go.microsoft.com/fwlink/?linkid=2227353&clcid=0x409&l=en-us&icid=nlweb), the [Azure CLI installed locally](https://learn.microsoft.com/cli/azure/install-azure-cli), and have Python 3.9+ installed locally.


## Local Setup

1. Clone or download this repository.
```
git clone https://github.com/microsoft/NLWeb
cd NLWeb
```

2. Create a virtual environment, replacing 'myenv' if you want a different name for your environment. 
```
python -m venv myenv
```

3. Activate the virtual environment - again, replace 'myenv' with the name you selected above, if different.   
```
source myenv/bin/activate    # Or on Windows: myenv\Scripts\activate
```

4. Install the dependencies.
```
cd code
pip install -r requirements.txt
```

5. Create an LLM resource and setup your service API keys.  

   If you want to use the Azure OpenAI service, follow the instructions below at [Azure OpenAI endpoint creation instructions](#azure-openai-endpoint-creation).  If you are participating in the private preview, the Azure AI Search API keys will be provided for you in a separate document.

   If you want to use Snowflake services, follow the instructions at [docs/Snowflake.md](docs/Snowflake.md).

   Then, copy the `.env.template` file into a new file named `.env` and add your keys for this resource into the .env file.

> Note: By default, we assume you are using an Azure OAI endpoint and the 4.1, 4.1-mini, and text-embedding-3-small models.  If you are using a different setup, this needs to be changed in the [config_llm.yaml](code\config\config_llm.yaml) file. Make sure to set the following:
   > - Preferred Provider:  By default, this is `azure_openai` - replace this with another provider listed within the file.
   > - Check your models:  For example, the default models for Azure OpenAI are 4.1 and 4.1-mini, but you may want to change these to 4o and 4o-mini (as an example).

6. Run a quick connectivity check:
```
python check_connectivity.py
```

7. If you are participating in the private preview, modify your local copy of the [config_nlweb.yaml](code\config\config_nlweb.yaml) to scope the `sites` to search over your website only.

8. Run the application locally:
```
python app-file.py
```

9. Navigate to the local site and start your chat:
- You can also experiment at http://localhost:8000/ or http://localhost:8000/static/nlwebsearch.html 
- Try different modes / sites at http://localhost:8000/static/str_chat.html

   > Note: Your site scope was set above in the [config_nlweb.yaml](code\config\config_nlweb.yaml) file


## Azure OpenAI Endpoint Creation

If you don't have an LLM endpoint already, you can follow these instructions to deploy a new endpoint with Azure OpenAI:

1. Create an Azure OpenAI resource at via the [portal](https://portal.azure.com/#create/Microsoft.CognitiveServicesOpenAI).  Use these [instructions](https://learn.microsoft.com/azure/cognitive-services/openai/how-to/create-resource) as a guide as needed.
> Notes:
> - Make sure you select a region where the models you want to use are available.  Refer to [AOAI Model Summary Table and Region Availability](https://learn.microsoft.com/azure/ai-services/openai/concepts/models?tabs=global-standard%2Cstandard-chat-completions#model-summary-table-and-region-availability) for more info.  To use the Azure OAI defaults of 4.1 and 4.1-mini in the [config_llm.yaml](code\config\config_llm.yaml), we recommend using `eastus2` or `swedencentral`.
> - If you are calling this endpoint locally, make the endpoint accessible from the internet in the network setup step.

2. Once your AOAI resource is created, you'll need to deploy your models within that resource.  This is done from Azure AI Foundry under [Deployments](https://ai.azure.com/resource/deployments). You can see instructions for this at [Azure AI Foundry - Deploy a Model](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#deploy-a-model).
   > Notes:
   > - Make sure the resource you created in the prior step is showing in the dropdown at the top left of the screen.
   > - You will need to repeat this step **3 times** to deploy three base models: `gpt-4.1`, `gpt-4.1-mini`, and `text-embedding-3-small`.


3. You'll need to add your Azure OpenAI endpoint and key to your .env file (see step 5 in [Local Setup](#local-setup) above). You can find the endpoint API key for the Azure OpenAI resource that you created above in the [Azure portal](https://portal.azure.com/?feature.msaljs=true#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/OpenAI), not [Azure AI Foundry](https://ai.azure.com) where you were deploying the models.  Click on the Azure OpenAI resource, and then in the left-hand sidebar under "Resource Management," select "Keys and Endpoint."   

![Screenshot of Keys and Endpoint under Resource Management in the Azure portal](images/AOAIKeysAndEndpoint.jpg)

For instructions on obtaining the required Azure service keys, see [this quickstart](https://learn.microsoft.com/azure/ai-services/openai/chatgpt-quickstart?tabs=api-key) or refer to the [Azure Search example](https://learn.microsoft.com/azure/search/search-security-api-keys) for step-by-step details.


## Deploying NLWeb to an Azure WebApp
Currently, while the repo is private, it is recommended to use option 2.  

### Option 1: Azure Portal Deployment

1. Create a [Web App in Azure Portal](https://portal.azure.com/?feature.msaljs=true#view/WebsitesExtension/AppServiceWebAppCreateV3Blade):
   - Create a new resource group and instance name.  
   - Publish: Code
   - Choose Python 3.13 as the runtime stack
   - Select Linux as the operating system
   - Select "East US 2" or "Sweden Central" as the region
   - Select "Premium V3 P1V3 (195 minimum ACU/vCPU, 8 GB memory, 2 vCPU)" as the pricing plan
   - No database is needed.  

2. Set up deployment source:
   - Choose GitHub or Azure DevOps
   - Connect to your repository
   - Set up continuous deployment

3. Configure application settings:
   - Add all the environment variables from `.env.template`
   - Set `WEBSITE_RUN_FROM_PACKAGE=1`
   - Set `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
   - Don't forget to click "Apply" after all app settings have beeen added to save your changes!  

4. Configure startup command to:
   ```
   startup.sh
   ```
   This can be found under "Settings" in the "Configuration" section.  It's in the default "General settings" tab.  Again, don't forget to click "Save" when you are done to save your changes.  

   ![Startup Command can be found in the Configuration pane under the General settings tab.](images/StartupCommand.jpg)

### Option 2: Azure CLI Deployment

1. Log in to Azure:
   ```bash
   az login
   ```

2. Create a resource group (if needed):
   ```bash
   az group create --name yourResourceGroup --location eastus2
   ```

3. Create an App Service Plan:
   ```bash
   az appservice plan create --name yourAppServicePlan --resource-group yourResourceGroup --sku P1v3 --is-linux
   ```

4. Create a Web App:
   ```bash
   az webapp create --resource-group yourResourceGroup --plan yourAppServicePlan --name yourWebAppName --runtime "PYTHON:3.13"
   ```

5. Configure environment variables; modify the below command to include all of the environment variables in your .env:
   ```bash
   az webapp config appsettings set --resource-group yourResourceGroup --name yourWebAppName --settings \
    AZURE_VECTOR_SEARCH_ENDPOINT="https://TODO.search.windows.net" \ 
    AZURE_VECTOR_SEARCH_API_KEY="TODO" \ 
    AZURE_OPENAI_ENDPOINT="https://TODO.openai.azure.com/" \ 
    AZURE_OPENAI_API_KEY="TODO" \ 
    WEBSITE_RUN_FROM_PACKAGE=1 \ 
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
   ```

6. Set startup command:
   ```bash
   az webapp config set --resource-group yourResourceGroup --name yourWebAppName --startup-file "startup.sh"
   ```

7. Deploy code using ZIP deployment:
   ```bash
   # Create a ZIP file of your project
   git archive --format zip --output ./app.zip main
   
   # Deploy the ZIP file
   az webapp deployment source config-zip --resource-group yourResourceGroup --name yourWebAppName --src ./app.zip
   ```

## Monitoring and Troubleshooting

### Logs
View logs in Azure Portal or using Azure CLI:
```bash
az webapp log tail --name yourWebAppName --resource-group yourResourceGroup
```

### Diagnostic Tools
Azure App Service provides diagnostic tools in the Azure Portal:
1. Go to your Web App
2. Navigate to "Diagnose and solve problems"
3. Choose from available diagnostics tools

### Health Check
The application includes a health endpoint at `/health` that returns a JSON response indicating service health.

## More Information

For more detailed information, see:
- [Azure App Service Documentation](https://docs.microsoft.com/en-us/azure/app-service/)
- [Python on App Service](https://docs.microsoft.com/en-us/azure/app-service/configure-language-python)
- Check the [Azure Web App Deployment Guide](./Azure_Web_App_Deployment_Guide.md) for detailed deployment instructions.


## Tests

To test your variables are correctly set to connect to Azure, see [azure-connectivity.py](code\azure-connectivity.py).  


## Deployment (CI/CD)

_At this time, the repository does not use continuous integration or produce a website, artifact, or anything deployed._

## Access

For questions about this GitHub project, please reach out to [NLWeb Support](mailto:NLWebSup@microsoft.com).

## Contributing

Please see [Contribution Guidance](CONTRIBUTING.md) for more information.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
