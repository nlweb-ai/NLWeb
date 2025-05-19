# Use the GitHub API to extract data from a repository
import requests
import json
import os
import logging
from dotenv import load_dotenv

# This script extracts data from a GitHub repository using the GitHub API.
# It retrieves information about the repository, issues, and pull requests.
# The extracted data is saved in JSON-LD format for NLWeb import.

# This is what you need for the JSON-LD output: @type, name, description, url

default_filename = "ghrepoinfo.json"
demo = True     # Settings for demo mode

def get_all_pages(url, headers, params=None):
    results = []
    page = 1
    while True:
        logging.debug(f"Fetching page {page} for URL: {url} with params: {params}") 
        req_params = {} if not params else params.copy()
        req_params.update({"per_page": 100, "page": page})
        resp = requests.get(url, headers=headers, params=req_params)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            logging.debug("No items returned, ending pagination")
            break
        results.extend(items)
        logging.debug(f"Page {page} returned {len(items)} items")
        page += 1
    return results


def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Starting GitHub data extraction")

    # Load environment variables from .env file
    load_dotenv()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        return

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Create a new file if it does not exist
    with open(default_filename, "w") as file:
        file.write("")  # Clear the file if it exists

    debug_size= {}
    
    # Get the repositories for the authenticated user
    repos = get_all_pages("https://api.github.com/user/repos", headers)
    logging.info(f"Found {len(repos)} repositories")
    for repo in repos:
        owner = repo["owner"]["login"]
        name = repo["name"]
        
        if demo:
            # Skip repos that are not owned by the user
            if owner != "jennifermarsman":
                continue
            # Skip repos that are not public
            if repo["visibility"] != "public":
                continue

        logging.info(f"Processing repo {owner}/{name}")
    
        # Copying over only a subset of information due to embedding model token limits
        repo_info = {
            "@type": "GithubRepository",
            "name": repo["full_name"],
            "description": repo.get("description", f"This is a GitHub repository created by {owner}"),
            "url": repo["html_url"],
            "owner": repo["owner"]["login"],
            "private": repo["private"],
            "fork": repo["fork"],
            "size": repo["size"],
            "stargazers_count": repo["stargazers_count"],
            #"watchers_count": repo["watchers_count"],
            "language": repo["language"],
            #"forks_count": repo["forks_count"],
            "archived": repo["archived"],
            "disabled": repo["disabled"],
            #"open_issues_count": repo["open_issues_count"],
            "license": repo["license"]["name"] if repo.get("license") else None,
            "allow_forking": repo["allow_forking"],
            "visibility": repo["visibility"],
            "forks": repo["forks"],
            "open_issues": repo["open_issues"],
            "watchers": repo["watchers"],
            "default_branch": repo["default_branch"],
        }
        # TODO: it would be cool to add collaborators, branches, tags, languages, stargazers, contributors, subscribers, downloads
        
        # Issues for this repo
        issues_url = f"https://api.github.com/repos/{owner}/{name}/issues"
        issues = get_all_pages(issues_url, headers, {"state": "all"})
        logging.info(f"Fetched {len(issues)} issues for {owner}/{name}")

        # Hack for demo to stay within model embedding token limits
        if demo:
            if len(issues) > 10:
                continue
        logging.info(f"Fetched {len(issues)} issues for {owner}/{name}")

        issues_info = []
        for issue in issues:
            issue_info = {
                "@type": "GithubIssue",
                "name": issue["title"],
                "description": issue.get("body", f"This is a GitHub issue"),
                "url": issue["html_url"],
                "user": issue["user"]["login"],
                "labels": issue["labels"],
                "state": issue["state"],
                "assignee": issue["assignee"]["login"] if issue.get("assignee") else None,
                "comments": issue["comments"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "closed_at": issue["closed_at"],
                "closed_by": issue["closed_by"]["login"] if issue.get("closed_by") else None,
                "reactions": issue["reactions"],
            }
            issues_info.append(issue_info)
        repo_info["issues"] = issues_info

        # Pull requests for this repo  
        pulls_url = f"https://api.github.com/repos/{owner}/{name}/pulls"
        pulls = get_all_pages(pulls_url, headers, {"state": "all"})
        logging.info(f"Fetched {len(pulls)} pull requests for {owner}/{name}")  # added
        pulls_info = []
        for pull in pulls:
            pull_info = {
                "@type": "GithubPullRequest",
                "name": pull["title"],
                "description": pull.get("body", f"This is a GitHub pull request"),
                "url": pull["html_url"],
                "number": pull["number"],
                "state": pull["state"],
                "user": pull["user"]["login"],
                "created_at": pull["created_at"],
                "updated_at": pull["updated_at"],
                "closed_at": pull["closed_at"],
                "merged_at": pull["merged_at"],
                "assignee": pull["assignee"]["login"] if pull.get("assignee") else None,
                "labels": pull["labels"],
                "draft": pull["draft"],
                "auto_merge": pull["auto_merge"],
            }
            pulls_info.append(pull_info)
        repo_info["pulls"] = pulls_info

        key = repo_info["name"]
        debug_size[key] = len(str(repo_info))

        with open(default_filename, "a", encoding="utf-8") as f:
            json.dump(repo_info, f)
            f.write("\n")

    logging.info(f"Wrote JSON-LD output to {default_filename}")  # added
    
    # Uncomment the following lines if you are having issues with token limits to see what the biggest repos are
    #max_value = max(debug_size.values())
    #max_keys = [key for key, value in debug_size.items() if value == max_value]
    #print("Keys with maximum value:", max_keys)
    #print("Maximum value:", max_value)

if __name__ == "__main__":
    main()
