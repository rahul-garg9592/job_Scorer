import requests

SERPAPI_KEY = "5bd7e457ed075e052059579de2bf5f0560d14ea0e7d91e5b3612b84b10b992a3"

def fetch_job_from_linkedin(linkedin_url):
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "linkedin_jobs",
        "url": linkedin_url
    }
    try:
        response = requests.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        data = response.json()

        job_info = {
            "job_title": data.get("job_title", ""),
            "company_name": data.get("company_name", ""),
            "location": data.get("location", ""),
            "job_description": data.get("description", ""),
            "experience_required": "",
            "tech_stack": [],
            "contact_info": []
        }

        return job_info

    except Exception as e:
        print(f"❌ Error fetching LinkedIn job: {e}")
        return None
