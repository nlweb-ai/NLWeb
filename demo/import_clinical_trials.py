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
    limit = 10
    i = 0

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

    for filename in os.listdir(json_dir):
        if filename.endswith(".json"):
            with open(os.path.join(json_dir, filename), "r", encoding="utf-8") as file:
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
                        logging.warning(f"And the malformed line was: {line}")
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
                #print(json.dumps(trial_info, indent=2, ensure_ascii=False))
                
                with open(os.path.join(processed_dir, filename), "w", encoding="utf-8") as f:
                    json.dump(trial_info, f)
                    f.write("\n")

                logging.info(f"Processed {filename}")

            # Break if we reach the limit
            i+=1
            if i >= limit:
                break


if __name__ == "__main__":
    main()
