
import time
import openai 
import numpy as np
import sys
import os
import glob

# Set your OpenAI API key
# Get OpenAI API key from environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")

client = openai.OpenAI()

EMBEDDINGS_PATH_SMALL = "/Users/guha/mahi/data/sites/embeddings/small"
EMBEDDINGS_PATH_LARGE = "/Users/guha/mahi/data/sites/embeddings/large"
EMBEDDINGS_PATH_COMPACT = "/Users/guha/mahi/data/sites/embeddings/compact"

EMBEDDING_MODEL_SMALL = "text-embedding-3-small"
EMBEDDING_MODEL_LARGE = "text-embedding-3-large"

JSONL_PATH = "/Users/guha/mahi/data/sites/jsonl/"
JSONL_PATH_COMPACT = "/Users/guha/mahi/data/sites/compact_jsonl/"

def get_embedding(text, model="text-embedding-3-small"):
   text = text.replace("\n", " ")
   return client.embeddings.create(input = [text], model=model).data[0].embedding


def read_file_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return None
    
def clean_utf8(text):
    return text.encode('utf-8', errors='ignore').decode('utf-8')

def process_files(input_file, size="small", model="text-embedding-3-small", num_to_process=10000000):
    num_done = 0
    if (size == "small"):
        output_path = EMBEDDINGS_PATH_SMALL + "/" + input_file + ".txt"
        model = EMBEDDING_MODEL_SMALL
    elif (size == "compact"):
        output_path = EMBEDDINGS_PATH_COMPACT + "/" + input_file + ".txt"
        model = EMBEDDING_MODEL_SMALL
    else:
        output_path = EMBEDDINGS_PATH_LARGE + "/" + input_file + ".txt"
        model = EMBEDDING_MODEL_LARGE

    input_path = JSONL_PATH + input_file + "_schemas.txt"

    if (size == "compact"):
        input_path = JSONL_PATH_COMPACT + input_file + "_schemas.txt"
    
    try:
        with open(input_path, 'r') as input_file, \
             open(output_path, 'w', encoding='utf-8') as output_file:
            
            batch = []
            batch_urls = []
            batch_jsons = []
            
            for line in input_file:
                # Skip empty lines
                if not line.strip():
                    continue
                
                line = clean_utf8(line)
                try:
                    # Split line by tab
                    url, json_str = line.strip().split('\t')
                    
                    batch_urls.append(url)
                    batch_jsons.append(json_str)
                    batch.append(json_str[0:6000])
                    num_done += 1
                    # Process batch when it reaches size 100
                    if len(batch) == 100 or (num_done > num_to_process):
                        # Get embeddings for the batch
                        embeddings = client.embeddings.create(input=batch, model=model).data
                        
                        # Write results for the batch
                        for i in range(len(batch)):
                            output_file.write(f"{batch_urls[i]}\t{batch_jsons[i]}\t{embeddings[i].embedding}\n")
                        print(f"Processed {num_done} lines")
                        # Clear the batches
                        batch = []
                        batch_urls = []
                        batch_jsons = []
                        time.sleep(5)
                except Exception as e:
                    print(f"Error processing line: {str(e)}")
                    continue
                if num_done > num_to_process:
                    break
            # Process any remaining items in the final batch
            if batch:
                embeddings = client.embeddings.create(input=batch, model=model).data
                for i in range(len(batch)):
                    output_file.write(f"{batch_urls[i]}\t{batch_jsons[i]}\t{embeddings[i].embedding}\n")
                    
    except Exception as e:
        print(f"Error processing files: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python embedding.py <input_file> <model>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    model = sys.argv[2] # "small" or "large" or "compact"
    
    if input_file == 'all':
        # Get all schema files in JSONL_PATH
        schema_files = glob.glob(os.path.join(JSONL_PATH, "*_schemas.txt"))
        
        for schema_file in schema_files:
            # Extract base filename without _schemas.txt
            base_name = os.path.basename(schema_file)[:-12]
            
            # Check if embedding file exists
            embedding_file = os.path.join(EMBEDDINGS_PATH_SMALL if model == "small" else EMBEDDINGS_PATH_LARGE, 
                                        base_name + ".txt")
            
            if not os.path.exists(embedding_file):
                print(f"Processing {base_name}")
                process_files(base_name, model)
            else:
                print(f"Skipping {base_name} - embedding file already exists")
    else:
        process_files(input_file, model)

