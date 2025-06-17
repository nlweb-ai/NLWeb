import requests
import json
import os
import logging
import codecs
#from dotenv import load_dotenv

# Download the latest version of this data from:
# https://clinicaltrials.gov/expert-search?term=Cancer
# Information on how to download: https://clinicaltrials.gov/data-api/how-download-study-records
# TODO: save as json - options screenshot
# Then extract from zip and point to the directory of json files

json_dir = "C:\\Users\\jennmar\\Downloads\\ctg-studies"

def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Starting clinical trial data import...")
    logging.info(f"Reading from JSON directory: {json_dir}")

    # Load environment variables from .env file
    #load_dotenv()
    #token = os.environ.get("GITHUB_TOKEN")
    #if not token:
    #    print("Error: GITHUB_TOKEN environment variable not set")
    #    return

    #headers = {
    #    "Authorization": f"token {token}",
    #    "Accept": "application/vnd.github.v3+json"
    #}

    limit = 5
    i = 0

    if not os.path.exists(json_dir):
        logging.error(f"Directory {json_dir} does not exist. Please check the path.")
        return
    
    processed_dir = os.path.join(json_dir, "processed")
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)

    for filename in os.listdir(json_dir):
        if filename.endswith(".json"):
            with open(os.path.join(json_dir, filename), "r", encoding="utf-8") as file:
                #data = json.load(file)
                #data = json.load(file, strict=False)  # Use strict=False to handle any JSON parsing issues

                # unescape backslashes
                #raw = file.read()
                #fixed = codecs.decode(raw, "unicode_escape", "replace")
                #data = json.loads(fixed)

                data = None
                total_data = None
                for line in file:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if total_data is None:
                            total_data = data
                        else:
                            total_data.update(data)
                    except json.JSONDecodeError as e:
                        logging.warning(f"Skipping malformed line in {filename}: {e}")
                        continue

                # Process the JSON data as needed
                trial_info = {
                    "@type": "CancerClinicalTrial",
                    # TODO: should I use brief title or official title?
                    # use merged total_data and fallback to briefTitle if officialTitle missing
                    "name": total_data["protocolSection"]["identificationModule"].get(
                        "officialTitle",
                        total_data["protocolSection"]["identificationModule"].get("briefTitle", "")
                    ),
                    "description": total_data["protocolSection"]["descriptionModule"].get("briefSummary", total_data["protocolSection"]["descriptionModule"].get("detailedDescription", "")),
                    "url": "https://clinicaltrials.gov/study/" + total_data["protocolSection"]["identificationModule"]["nctId"],
                    "content": total_data, #json.dumps(data, ensure_ascii=False),
                }
                print(json.dumps(trial_info, indent=2, ensure_ascii=False))

                # Copy the rest of the "data" json into trial_info
                #trial_info.update(data)
                
                with open(os.path.join(processed_dir, filename), "w", encoding="utf-8") as f:
                    json.dump(trial_info, f)
                    f.write("\n")

                logging.info(f"Processed {filename}")

            # Break if we reach the limit
            i+=1
            if i >= limit:
                break

    
    # Uncomment the following lines if you are having issues with token limits to see what the biggest items are
    #max_value = max(debug_size.values())
    #max_keys = [key for key, value in debug_size.items() if value == max_value]
    #print("Keys with maximum value:", max_keys)
    #print("Maximum value:", max_value)

if __name__ == "__main__":
    main()
