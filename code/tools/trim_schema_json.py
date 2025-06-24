import json
import chardet

# the schema.org markup on many pages includes a lot of information that is not useful
# for indexing or ranking. Further, many pages are just collections that we don't 
# want to index at all. We can also skip things like Breadcrumbs

skip_types = ["ListItem", "ItemList", "Organization", "BreadcrumbList", "Breadcrumb", "WebSite", 
              "SearchAction", "SiteNavigationElement", "WebPageElement", "WebPage", "NewsMediaOrganization",
              "MerchantReturnPolicy", "ReturnPolicy", "CollectionPage", "Brand", "Corporation", 
              "SiteNavigationElement", "ReadAction"]

skip_properties = ["publisher", "mainEntityOfPage"]

def should_skip_item(site, item):
    if item is None:
        return True
    if "@type" in item and item["@type"] in skip_types:
        return True
    # Check if @type is a list and if any value in the list is in skip_types
    elif "@type" in item and isinstance(item["@type"], list):
        for type_value in item["@type"]:
            if type_value in skip_types:
                return True
    elif "@type" not in item:
        print(f"Warning: Item without @type field found for site {site}, keeping item: {str(item)[:100]}...")
        return False
    return False

# trim the markup without loosing too much of the information that the LLM can use
# go through each property in the schema_json and apply the following rules to construct
# a new json object with only the properties that are useful for indexing and ranking.
# 1. If the property is in skip_properties, remove it from the schema_json. 
# 2. If the property is image and the value is a list of urls, pick the first value
# 3. If the property is image and the value is an ImageObject, pick the url of the image
# 4. If the value is a json object of type Person, pick the name 
# 5. If the value is aggregateRating, pick the ratingValue
# 6. If the propery is review and the value is a list, go through each item in the list
# and pick the reviewBody of upto 3 reviews, with the longest reviews

def trim_schema_json_list(schema_json, site):
    trimmed_items = []
    for item in schema_json:
        trimmed_item = trim_schema_json(item, site)
        if trimmed_item is not None:
            trimmed_items.append(trimmed_item)
    return trimmed_items or None

def trim_schema_json(schema_json, site):
    if schema_json is None:
        return None
    if isinstance(schema_json, list):
        return trim_schema_json_list(schema_json, site)
    elif (isinstance(schema_json, dict) and "@graph" in schema_json):
        trimmed_items = trim_schema_json_list(schema_json["@graph"], site)
        if (len(trimmed_items) > 0):
            #schema_json["@graph"] = trimmed_items
            return trimmed_items
        else:   
            return None
    elif isinstance(schema_json, dict):
        if (should_skip_item(site, schema_json)):
            return None
        else:
            retval = {}
            # Rule 1: Skip properties in skip_properties
            for k, v in schema_json.items():
                if k in skip_properties:
                    continue
                
                # Rule 2: If property is image and value is a list of URLs, pick the first value
                if k == "image" and isinstance(v, list) and len(v) > 0:
                    if all(isinstance(img, str) for img in v):
                        retval[k] = v[0]
                        continue
                
                # Rule 3: If property is image and value is an ImageObject, pick the URL
                if k == "image" and isinstance(v, dict) and v.get("@type") == "ImageObject" and "url" in v:
                    retval[k] = v["url"]
                    continue
                
                # Rule 4: If value is a Person object, pick the name
                if isinstance(v, dict) and v.get("@type") == "Person" and "name" in v:
                    retval[k] = v["name"]
                    continue
                
                # Rule 5: If value is aggregateRating, pick the ratingValue
                if k == "aggregateRating" and isinstance(v, dict) and "ratingValue" in v:
                    retval[k] = v["ratingValue"]
                    continue
                
                # Rule 7: If property is review and value is a list, pick up to 3 longest reviewBodies
                if k == "review" and isinstance(v, list):
                    reviews = []
                    review_bodies = [(r.get("reviewBody", ""), r) for r in v if isinstance(r, dict) and "reviewBody" in r]
                    # Sort by length of reviewBody in descending order
                    review_bodies.sort(key=lambda x: len(x[0]), reverse=True)
                    # Take up to 3 longest reviews
                    for _, review in review_bodies[:3]:
                        reviews.append(review)
                    if reviews:
                        retval[k] = reviews
                        continue
                
                # Default: keep the property as is
                retval[k] = v
            
            # Return early since we've already processed all items
            return retval

def detect_encoding(file_path):
    """
    Detect the encoding of a file, with special handling for UTF-16.
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        String indicating the detected encoding
    """
    with open(file_path, 'rb') as f:
        # Read the first few bytes to check for BOM
        first_bytes = f.read(4)
        # Check for UTF-16 BOM (Little Endian)
        if first_bytes.startswith(b'\xff\xfe'):
            return 'utf-16-le'
        # Check for UTF-16 BOM (Big Endian)
        elif first_bytes.startswith(b'\xfe\xff'):
            return 'utf-16-be'
        # Check for UTF-8 BOM
        elif first_bytes.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        # Reset file pointer and use chardet for other encodings
        f.seek(0)
        raw_data = f.read(10000)  # Read a chunk for detection
        result = chardet.detect(raw_data)
        return result['encoding']

def process_binary_file(file_path, output_file):
    """
    Process a file in binary mode for cases where text encoding is problematic.
    Specifically handles UTF-16 encoded files.
    """
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            
            # Check for UTF-16 LE BOM
            if content.startswith(b'\xff\xfe'):
                encoding = 'utf-16-le'
                content = content[2:]  # Skip BOM
            # Check for UTF-16 BE BOM
            elif content.startswith(b'\xfe\xff'):
                encoding = 'utf-16-be'
                content = content[2:]  # Skip BOM
            else:
                # Default to UTF-16 LE if no BOM
                encoding = 'utf-16-le'
            
            try:
                text = content.decode(encoding)
                
                # Process lines
                lines = text.split('\n')
                with open(output_file, 'w', encoding='utf-8') as out:
                    for line in lines:
                        if not line.strip():
                            continue
                            
                        parts = line.strip().split('\t')
                        if len(parts) != 2:
                            continue
                        
                        url, schema_json_str = parts
                        site = url.split("/")[2].replace("www.", "").replace(".com", "")
                        
                        # Clean up the JSON string - remove ^@ and similar artifacts
                        json_str = schema_json_str.replace("#N#", ' ').replace('^@', '')
                        
                        # Process as normal
                        try:
                            schema_json = json.loads(json_str)
                            # Continue with normal processing
                            if not isinstance(schema_json, list):
                                continue
                            
                            if isinstance(schema_json[0], list):
                                schema_json = schema_json[0]
                                
                            trimmed_json = []
                            for item in schema_json:
                                try:
                                    trimmed_item = trim_schema_json(item, site)
                                    if trimmed_item is not None:
                                        trimmed_json.append(trimmed_item)
                                except Exception as e:
                                    print(f"Error processing item in binary mode for {url}: {str(e)}")
                                    continue
                                    
                            if trimmed_json and len(trimmed_json) > 0:
                                out_line = f"{url}\t{json.dumps(trimmed_json)}\n"
                                out.write(out_line)
                            else:
                                print(f"Binary mode: No items processed for {url}")
                                
                        except Exception as e:
                            print(f"Error processing binary data from {url}: {str(e)}")
            except UnicodeDecodeError as e:
                print(f"Failed to decode with {encoding}: {str(e)}")
    except Exception as e:
        print(f"Binary processing failed: {str(e)}")

def trim_schema_json_file(file_path, output_file):
    """
    Process a file containing schema.org JSON data and trim it according to rules.
    Handles different text encodings including UTF-16.
    
    Args:
        file_path: Path to the input file with URL and JSON data tab-separated
        output_file: Path to write the trimmed results
    """
    try:
        # Detect the encoding of the file
        encoding = detect_encoding(file_path)
        print(f"Detected encoding: {encoding}")
        
        # For UTF-16 files, use binary processing method
        if encoding and encoding.startswith('utf-16'):
            print(f"Using binary processing for UTF-16 encoded file")
            process_binary_file(file_path, output_file)
            return
        
        # Normal processing for UTF-8 and other encodings
        with open(file_path, 'r', encoding=encoding or 'utf-8', errors='replace') as f:
            with open(output_file, 'w', encoding='utf-8') as out:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) != 2:
                        continue
                    
                    url, schema_json_str = parts
                    site = url.split("/")[2].replace("www.", "").replace(".com", "")
                    try:
                        # Handle special characters in JSON string
                        json_str = schema_json_str.replace("#N#", ' ')
                        schema_json = json.loads(json_str)
                        # schema_json should be a list
                        if not isinstance(schema_json, list):
                            continue
                        # some sites double list it
                        if isinstance(schema_json[0], list):
                            schema_json = schema_json[0]
                        trimmed_json = []
                        for item in schema_json:
                            try:
                                trimmed_item = trim_schema_json(item, site)

                                if trimmed_item is not None:
                                    trimmed_json.append(trimmed_item)
                                else:
                                    print(f"Null trimmed item for {item}")
                            except Exception as e:
                                print(f"Error processing {url}: {str(e)}")
                                continue
                        if trimmed_json is not None and len(trimmed_json) > 0:
                            out_line = f"{url}\t{json.dumps(trimmed_json)}\n"
                            out.write(out_line)
                        else:
                            print(f"Skipping {url} because no items were processed")
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for {url}: {str(e)}")
                        continue
                    except Exception as e:
                        print(f"Error processing {url}: {str(e)}")
                        continue
    except UnicodeDecodeError as e:
        print(f"Encoding detection failed, trying binary mode: {str(e)}")
        # Fallback to binary processing for difficult files
        process_binary_file(file_path, output_file)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise

if __name__ == "__main__":
    import sys
    import os
    
    if len(sys.argv) != 2:
        print("Usage: python trim_schema_json.py <input_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Construct output filename by appending _trimmed before the extension
    file_name, file_ext = os.path.splitext(input_file)
    output_file = f"{file_name}_trimmed{file_ext}"
    
    print(f"Processing {input_file} -> {output_file}")
    trim_schema_json_file(input_file, output_file)
    print("Done!")