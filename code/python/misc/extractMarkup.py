import json
from bs4 import BeautifulSoup
import sys
import os

def extract_schema_markup(html_file):
    # Read the HTML file
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all script tags with type "application/ld+json"
    schema_tags = soup.find_all('script', type='application/ld+json')
    
    schemas = []
    for tag in schema_tags:
        try:
            # Parse JSON content
            schema = json.loads(tag.string)
            schemas.append(schema)
        except json.JSONDecodeError as e:
            print(f"Error parsing schema JSON: {e}")
            continue
    # Convert schemas list to a single line string
    schema_str = json.dumps(schemas, separators=(',', ':'))
    return schema_str

def extract_canonical_url(html_file):
    # Read the HTML file
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find canonical link tag
    canonical_tag = soup.find('link', {'rel': 'canonical'})
    
    if canonical_tag and 'href' in canonical_tag.attrs:
        return canonical_tag['href']
    
    # If no canonical tag found, return None
    return None



def get_files_in_directory(directory):
    # Check if directory exists
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return []
        
    # Get list of all files in directory
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        return files
    except Exception as e:
        print(f"Error accessing directory {directory}: {str(e)}")
        return []

def process_directory(directory):
    # Get list of files
    files = get_files_in_directory(directory)
    
    # Create output filename in parent directory
    dir_name = os.path.basename(directory)
    parent_dir = os.path.dirname(directory)
    output_file = os.path.join(parent_dir + "/jsonl/", f"{dir_name}_schemas.txt")
    files_processed = 0
    urls_written = 0
    # Process each file and write results
    with open(output_file, 'w', encoding='utf-8') as f:
        for html_file in files:
            try:
                # Extract canonical URL and schemas
                canonical_url = extract_canonical_url(html_file)
                schemas = extract_schema_markup(html_file)
                
                # Skip if no canonical URL found
                if not canonical_url:
                    # Check schemas for URL field
                    url_from_schema = None
                    if schemas:
                        try:
                            schema_list = json.loads(schemas)
                            for schema in schema_list:
                                if isinstance(schema, dict) and 'url' in schema:
                                    url_from_schema = schema['url']
                                    break
                        except json.JSONDecodeError:
                            pass
                    
                    # Use schema URL if found, otherwise keep as None
                    canonical_url = url_from_schema 
                    if not canonical_url:
                        print(f"No canonical URL found in {html_file}, skipping...")
                        continue
                    
                # Write tab-separated line to output file
                urls_written += 1
                f.write(f"{canonical_url}\t{schemas}\n")
                #print(f"{canonical_url}\t{schemas}\n")
                files_processed += 1
                # Print progress, using \r to overwrite previous line
                print(f"\rFiles processed: {files_processed}, URLs written: {urls_written}", end='', flush=True)
            except Exception as e:
                print(f"Error processing {html_file}: {str(e)}")
                continue
    
    return output_file


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extractMarkup.py <directory>")
        sys.exit(1)
        
    directory = sys.argv[1]
    #print(extract_schema_markup(directory))
    process_directory(directory)
