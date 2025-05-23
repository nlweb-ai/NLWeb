# code/tools/ats_data_loader.py
import asyncio
import os
import sys
import json
import uuid

# Add the parent directory of 'tools' to sys.path to allow imports from 'code'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # This should be the 'code' directory
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "tools"))

from tools.db_load import loadJsonToDB, delete_site_from_database
from config.config import CONFIG

ATS_JOBS_SITE_NAME = "ats_jobs"
ATS_JOB_ITEM_TYPE = "{http://schema.org/}JobPosting"

ATS_CANDIDATES_SITE_NAME = "ats_candidates"
ATS_CANDIDATE_ITEM_TYPE = "{http://schema.org/}Person"

SAMPLE_DATA_DIR = os.path.join(project_root, "ats_sample_data")
# Define a directory for temporary files created by the application
APP_TEMP_DATA_DIR = os.path.join(project_root, "temp_ats_data") # Renamed from ats_temp_data for consistency
os.makedirs(APP_TEMP_DATA_DIR, exist_ok=True)


async def _load_data_files(file_paths: list, site_name: str, delete_existing: bool = False, batch_size: int = 10):
    """
    Generic function to load data from a list of JSON file paths into the specified site.
    """
    print(f"--- Loading data for site: {site_name} from {len(file_paths)} files ---")
    first_file = True
    for file_path in file_paths:
        if os.path.exists(file_path):
            print(f"Loading data from: {file_path}")
            await loadJsonToDB(
                file_path=file_path,
                site=site_name,
                batch_size=batch_size,
                delete_existing=delete_existing if first_file else False,
                force_recompute=True, # Force recompute for consistency
                database=CONFIG.preferred_retrieval_endpoint
            )
            if first_file:
                first_file = False
        else:
            print(f"Warning: Data file not found: {file_path}")
    print(f"--- Data Loading Complete for site: {site_name} ---")

async def load_job_postings_from_sample_data(delete_existing: bool = False):
    """Loads predefined job postings from the SAMPLE_DATA_DIR."""
    print(f"--- Loading Sample Job Postings for site: {ATS_JOBS_SITE_NAME} ---")
    job_files = [
        os.path.join(SAMPLE_DATA_DIR, "job_posting_1.json"),
        os.path.join(SAMPLE_DATA_DIR, "job_posting_2.json")
    ]
    await _load_data_files(job_files, ATS_JOBS_SITE_NAME, delete_existing)
    print("--- Sample Job Postings Loading Complete ---")

async def load_candidate_profiles_from_sample_data(delete_existing: bool = False):
    """Loads predefined candidate profiles from the SAMPLE_DATA_DIR."""
    print(f"--- Loading Sample Candidate Profiles for site: {ATS_CANDIDATES_SITE_NAME} ---")
    candidate_files = [
        os.path.join(SAMPLE_DATA_DIR, "candidate_profile_1.json"),
        os.path.join(SAMPLE_DATA_DIR, "candidate_profile_2.json")
    ]
    await _load_data_files(candidate_files, ATS_CANDIDATES_SITE_NAME, delete_existing)
    print("--- Sample Candidate Profiles Loading Complete ---")

async def add_job_posting_data(job_data_list: list, site_name: str = ATS_JOBS_SITE_NAME, delete_existing: bool = False):
    """
    Adds new job posting data to the database.
    job_data_list: A list of dictionaries, where each dictionary is a job posting.
    Saves data to temporary files before loading.
    """
    print(f"--- Adding {len(job_data_list)} Job Posting(s) to site: {site_name} ---")
    
    temp_files_created = []
    file_paths_to_load = []

    try:
        for i, job_data in enumerate(job_data_list):
            if 'id' not in job_data or not job_data['id']:
                job_data['id'] = f"job_{uuid.uuid4()}"
            
            temp_file_name = f"temp_job_{job_data['id']}.json"
            temp_file_path = os.path.join(APP_TEMP_DATA_DIR, temp_file_name)
            
            with open(temp_file_path, 'w') as f:
                json.dump(job_data, f, indent=2)
            temp_files_created.append(temp_file_path)
            file_paths_to_load.append(temp_file_path)

        if file_paths_to_load:
            await _load_data_files(file_paths_to_load, site_name, delete_existing, batch_size=len(file_paths_to_load))
            print(f"--- {len(job_data_list)} Job Posting(s) processing attempted ---")
        else:
            print("--- No job posting data provided to add. ---")

    except Exception as e:
        print(f"Error during add_job_posting_data: {e}")
    finally:
        for temp_file in temp_files_created:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print(f"Cleaned up temp file: {temp_file}")
                except OSError as e:
                    print(f"Error cleaning up temp file {temp_file}: {e}")

async def add_candidate_profile_data(candidate_data_list: list, site_name: str = ATS_CANDIDATES_SITE_NAME, delete_existing: bool = False):
    """
    Adds new candidate profile data to the database.
    candidate_data_list: A list of dictionaries, where each dictionary is a candidate profile.
    Saves data to temporary files before loading.
    """
    print(f"--- Adding {len(candidate_data_list)} Candidate Profile(s) to site: {site_name} ---")
    
    # APP_TEMP_DATA_DIR is already created at the module level.
    # if not os.path.exists(APP_TEMP_DATA_DIR):
    #     os.makedirs(APP_TEMP_DATA_DIR)

    temp_files_created = []
    file_paths_to_load = [] # Changed from processed_candidates to align with add_job_posting_data

    try:
        for i, cand_data in enumerate(candidate_data_list):
            if "id" not in cand_data or not cand_data["id"]:
                cand_data["id"] = f"cand_{uuid.uuid4()}"
            # No need to append to processed_candidates, directly create file
            
            temp_file_name = f"temp_cand_{cand_data['id']}.json"
            temp_file_path = os.path.join(APP_TEMP_DATA_DIR, temp_file_name)
            
            try:
                with open(temp_file_path, 'w') as f:
                    json.dump(cand_data, f, indent=2)
                temp_files_created.append(temp_file_path)
                file_paths_to_load.append(temp_file_path) # Add to file_paths_to_load
            except Exception as e:
                print(f"Error writing temporary candidate file {temp_file_path}: {e}")
                # Decide if you want to continue with other candidates or raise

        if not file_paths_to_load: # Check file_paths_to_load instead of temp_files_created for consistency
            print("No valid candidate data to load.")
            return

        # Call the generic loading function for these temp files
        await _load_data_files(
            file_paths=file_paths_to_load, # Use file_paths_to_load
            site_name=site_name,
            delete_existing=delete_existing,
            batch_size=len(file_paths_to_load) # Consistent batch sizing
        )
        print(f"--- {len(file_paths_to_load)} Candidate Profile(s) processing attempted ---")

    except Exception as e:
        print(f"Error during add_candidate_profile_data: {e}")
    finally:
        for temp_file in temp_files_created: # This part is fine
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print(f"Cleaned up temp file: {temp_file}")
                except OSError as e: # Catch OSError specifically for os.remove issues
                    print(f"Error cleaning up temp file {temp_file}: {e}")

async def main():
    await load_job_postings_from_sample_data(delete_existing=True)
    await load_candidate_profiles_from_sample_data(delete_existing=True)

    # Example of using add_candidate_profile_data (optional, for testing)
    # test_candidate = [{
    #     "id": "cand_test_001", "name": "Test Candidate from Main", 
    #     "resume_text": "This is a test resume.", "skills": ["testing"]
    # }]
    # await add_candidate_profile_data(test_candidate, ATS_CANDIDATES_SITE_NAME)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    os.environ["NLWEB_APP_PATH"] = project_root
    
    asyncio.run(main())
