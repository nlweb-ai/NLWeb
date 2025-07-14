#!/usr/bin/env python3

import json
import requests
import urllib.parse

def main():
    # Prompt for query
    query = input("Enter your query: ")
    if not query:
        print("Query cannot be empty. Exiting.")
        return
    
    # Prompt for site with default
    site = input("Enter site (press Enter for 'all'): ")
    if not site:
        site = "all"
        print(f"Using default site: {site}")
    
    # Prompt for server with default
    server = input("Enter server (press Enter for 'localhost:8000'): ")
    if not server:
        server = "localhost:8000"
        print(f"Using default server: {server}")
    
    # Encode the query
    print("Encoding query...")
    encoded_query = urllib.parse.quote(query)
    
    # Construct the URL
    url = f"http://{server}/ask"
    params = {
        "query": encoded_query,
        "site": site,
        "model": "auto",
        "prev": "[]",
        "item_to_remember": "",
        "context_url": "",
        "streaming": "false"
    }
    
    # Make the request
    print(f"Contacting server at http://{server}...")
    print(f"Sending query: \"{query}\" for site: \"{site}\"...")
    
    try:
        response = requests.get(url, params=params)
        print("Response received. Processing data...")
        
        # Check if response is successful
        if response.status_code != 200:
            print(f"Error: Server returned status code {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        # Parse JSON
        print("Parsing JSON response...")
        try:
            data = response.json()
        except json.JSONDecodeError:
            print("Failed to parse JSON response")
            print(f"Raw response: {response.text}")
            return
        
        # Extract and print results
        print("Extracting results...")
        if 'results' in data:
            results = data['results']
            print(f"Found {len(results)} results.")
            print("\nResults:")
            print("========")
            
            for i, item in enumerate(results, 1):
                name = item.get('name', 'No name available')
                description = item.get('description', 'No description available')
                print(f"{i}. {name}")
                print(f"   {description}\n")
        else:
            print("No 'results' field found in the response")
            print(f"Response keys: {list(data.keys())}")
        
        print("Done!")
        
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to server: {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")