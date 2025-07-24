import requests
import json
import os
import logging

# Download the latest version of this data from:
# https://clinicaltrials.gov/expert-search?term=Cancer
# Information on how to download: https://clinicaltrials.gov/data-api/how-download-study-records
# Then extract from zip and point to the directory of json files

# Replace this value with the location where you have extracted the JSON files.
json_dir = "C:\\Data\\ctg-studies"

def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Starting clinical trial data import...")
    logging.info(f"Reading from JSON directory: {json_dir}")

    # Use a limit if you want to process only a subset of files
    #limit = 500
    #i = 0

    instructions = "Full instructions are available at https://github.com/microsoft/NLWeb/tree/main/demo#ask-questions-of-clinical-trial-data."
    if not json_dir:
        logging.error("Please set the json_dir variable in import_clinical_trials.py to the directory containing the JSON files that you extracted.  " + instructions)
        return

    if not os.path.exists(json_dir):
        logging.error(f"Directory {json_dir} does not exist. Please check the path. " + instructions)
        return
    
    processed_dir = os.path.join(json_dir, "processed")
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)

    count = 0
    for filename in os.listdir(json_dir):
        if filename.endswith(".json"):
            with open(os.path.join(json_dir, filename), "r", encoding="utf-8") as file:
                total_data = None
                # Read entire file and parse JSON in one go
                raw = file.read()
                try:
                    total_data = json.loads(raw)
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON in {filename}: {e}")
                    continue

                # Process the JSON data as needed
                trial_info = {
                    "@type": "CancerClinicalTrial",
                    "name": total_data["protocolSection"]["identificationModule"].get(
                        "briefTitle",
                        total_data["protocolSection"]["identificationModule"].get("officialTitle", "")
                    ),
                    "description": total_data["protocolSection"]["descriptionModule"].get("briefSummary", total_data["protocolSection"]["descriptionModule"].get("detailedDescription", "")),
                    "url": "https://clinicaltrials.gov/study/" + total_data["protocolSection"]["identificationModule"]["nctId"],
                    "content": total_data, #json.dumps(data, ensure_ascii=False),
                }
                #print(json.dumps(trial_info, indent=2, ensure_ascii=False))
                
                with open(os.path.join(processed_dir, filename), "w", encoding="utf-8") as f:
                    json.dump(trial_info, f)     # TODO: check if this is being formatted correctly for line by line processing on read
                    f.write("\n")

                logging.info(f"Processed {filename}")
                count += 1

            # Break if we reach the limit
            #i+=1
            #if i >= limit:
            #    break

    logging.info(f"Processed {count} files in total.")

if __name__ == "__main__":
    main()
