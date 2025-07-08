
import sys
import os
import asyncio
import json

# Import common utilities from the repository
from core.embedding import get_embedding, batch_get_embeddings
from misc.logger.logging_config_helper import get_configured_logger

logger = get_configured_logger("scraping_embedding")

# Default model names
EMBEDDING_MODEL_SMALL = "text-embedding-3-small"
EMBEDDING_MODEL_LARGE = "text-embedding-3-large"

async def get_embedding_async(text, model="text-embedding-3-small"):
    """Get embedding using the common embedding utilities"""
    try:
        # Use the embedding wrapper from the repository
        return await get_embedding(text, model=model)
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        raise


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

async def process_files(input_file, output_dir, size="small", model=None, num_to_process=10000000):
    """Process files and generate embeddings"""
    num_done = 0
    
    # Determine model based on size if not provided
    if not model:
        if size == "small" or size == "compact":
            model = EMBEDDING_MODEL_SMALL
        else:
            model = EMBEDDING_MODEL_LARGE
    
    # Create output path
    output_filename = f"{os.path.basename(input_file).replace('_schemas.txt', '')}_embeddings.txt"
    output_path = os.path.join(output_dir, output_filename)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        with open(input_file, 'r') as infile, \
             open(output_path, 'w', encoding='utf-8') as output_file:
            
            batch_texts = []
            batch_urls = []
            batch_jsons = []
            
            for line in infile:
                # Skip empty lines
                if not line.strip():
                    continue
                
                line = clean_utf8(line)
                try:
                    # Split line by tab
                    url, json_str = line.strip().split('\t')
                    
                    batch_urls.append(url)
                    batch_jsons.append(json_str)
                    batch_texts.append(json_str[0:6000])  # Truncate for embedding
                    num_done += 1
                    
                    # Process batch when it reaches size 100
                    if len(batch_texts) == 100 or (num_done > num_to_process):
                        # Get embeddings for the batch
                        logger.info(f"Processing batch of {len(batch_texts)} items")
                        embeddings = await batch_get_embeddings(batch_texts, model=model)
                        
                        # Write results for the batch
                        for i in range(len(batch_texts)):
                            embedding_str = json.dumps(embeddings[i])
                            output_file.write(f"{batch_urls[i]}\t{batch_jsons[i]}\t{embedding_str}\n")
                        
                        logger.info(f"Processed {num_done} lines")
                        
                        # Clear the batches
                        batch_texts = []
                        batch_urls = []
                        batch_jsons = []
                        
                        # Small delay to avoid rate limits
                        await asyncio.sleep(2)
                        
                except Exception as e:
                    logger.error(f"Error processing line: {str(e)}")
                    continue
                    
                if num_done > num_to_process:
                    break
                    
            # Process any remaining items in the final batch
            if batch_texts:
                embeddings = await batch_get_embeddings(batch_texts, model=model)
                for i in range(len(batch_texts)):
                    embedding_str = json.dumps(embeddings[i])
                    output_file.write(f"{batch_urls[i]}\t{batch_jsons[i]}\t{embedding_str}\n")
                logger.info(f"Processed final batch, total: {num_done} lines")
                    
    except Exception as e:
        logger.error(f"Error processing files: {str(e)}")
        raise

def main():
    if len(sys.argv) < 3:
        print("Usage: python embedding.py <input_file> <output_dir> [model_size]")
        print("  input_file: Path to the schema file")
        print("  output_dir: Directory to save embeddings")
        print("  model_size: 'small' or 'large' (default: small)")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    model_size = sys.argv[3] if len(sys.argv) > 3 else "small"
    
    # Run the async function
    asyncio.run(process_files(input_file, output_dir, size=model_size))

if __name__ == "__main__":
    main()

