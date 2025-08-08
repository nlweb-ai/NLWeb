# Setting Up AWS Bedrock Foundation Models

This guide walks through the process of setting up AWS Bedrock foundational models, from enabling the models in the AWS console to configuring IAM permissions and obtaining the necessary credentials for boto3 integration.

## Table of Contents

1. [Enabling AWS Bedrock](#enabling-aws-bedrock)
2. [Requesting Access to Foundation Models](#requesting-access-to-foundation-models)
3. [Setting Up IAM Permissions](#setting-up-iam-permissions)
4. [Creating API Credentials](#creating-api-credentials)
5. [Configuring boto3 for AWS Bedrock](#configuring-boto3-for-aws-bedrock)

## Enabling AWS Bedrock

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/)
2. In the search bar at the top, type "Bedrock" and select the Amazon Bedrock service
3. If this is your first time using Bedrock, you'll see a welcome page. Click "Get started"
4. Select your preferred AWS region from the dropdown in the top-right corner (note that AWS Bedrock is not available in all regions)
5. You'll be directed to the Amazon Bedrock console dashboard

## Requesting Access to Foundation Models

Before you can use any foundation models, you need to request access:

1. In the Bedrock console, navigate to "Model access" in the left sidebar
2. You'll see a list of available foundation models from providers like Amazon, Anthropic, AI21 Labs, Cohere, Meta, and others
3. Select the checkboxes next to the models you want to use (e.g., Claude, Llama 2, Amazon Titan)
4. Click "Request model access" at the bottom of the page
5. Review the terms and conditions, then click "Request model access" again
6. Wait for approval (this is usually immediate for most models)
7. Once approved, the status will change to "Access granted"

## Setting Up IAM Permissions

To use AWS Bedrock programmatically, you need to create an IAM user or role with appropriate permissions:

1. Navigate to the [IAM console](https://console.aws.amazon.com/iam/)
2. Create a new policy:
   - Click "Policies" in the left sidebar, then "Create policy"
   - Switch to the JSON tab and paste the following policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel",
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": "*"
        }
    ]
}
```

   - Click "Next", name your policy (e.g., "BedrockAccess"), add a description, and click "Create policy"

3. Create a new IAM user or update an existing one:
   - Click "Users" in the left sidebar
   - Create a new user or select an existing one
   - Under "Permissions", click "Add permissions"
   - Choose "Attach policies directly"
   - Search for and select the "BedrockAccess" policy you created
   - Click "Next" and then "Add permissions"

## Creating API Credentials

To use AWS Bedrock with boto3, you need API credentials:

1. In the IAM console, navigate to the user you created or updated
2. Go to the "Security credentials" tab
3. Under "Access keys", click "Create access key"
4. Select "Command Line Interface (CLI)" as the use case
5. Acknowledge the recommendation and click "Next"
6. (Optional) Add a description tag and click "Create access key"
7. You'll see your Access Key ID and Secret Access Key. **Important**: This is the only time you'll see the Secret Access Key, so make sure to save it securely
8. Download the .csv file or copy both keys to a secure location
9. In order to support the LLMProvider interface, you will need to add the Access Key ID and Secret Access Key and Region to your environment variables:
    9.1. Concatenate the Access Key ID and Secret Access Key with a colon (:) and add it to the environment variable AWS_BEDROCK_API_KEY
    9.2. Add the region to the environment variable AWS_BEDROCK_REGION

## Supported Foundation Models

AWS Bedrock provides access to various foundation models, currently supported models are:

- **Amazon**: amazon.nova-..., amazon.titan-text-...
- **AI21 Labs**: ai21...
- **Anthropic**: anthropic.claude-...
- **Cohere**: cohere.command-...
- **Meta**: meta.llama3...
- **Mistral**: mistral...

For embedding models, currently supported models are:

- **Amazon**: amazon.titan-embed...
- **Cohere**: cohere.embed-...

Each model has different capabilities, pricing, and parameter options. Refer to the [AWS Bedrock documentation](https://docs.aws.amazon.com/bedrock/) for detailed information about each model.

## Monitoring and Cost Management

1. Monitor your usage in the AWS Billing console
2. Set up AWS Budgets to get alerts when costs exceed thresholds
3. Consider implementing token counting and rate limiting in your application

## Troubleshooting

Common issues and solutions:

- **Access Denied Errors**: Verify that your IAM permissions are correctly set up
- **Model Not Found**: Ensure you've requested and been granted access to the model
- **Region Issues**: Confirm that the model is available in your selected region
- **Quota Limits**: Check if you've hit your quota limits and request increases if needed

For more information, refer to the [AWS Bedrock documentation](https://docs.aws.amazon.com/bedrock/).
