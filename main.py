import gradio as gr
import google.generativeai as genai
import json
import re
import os

# --------------------------------------
# Setup Gemini Flash Model
# --------------------------------------
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise EnvironmentError("Please set GOOGLE_API_KEY environment variable.")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# --------------------------------------
# Extract structured job info from text
# --------------------------------------
def extract_job_from_text(message):
    prompt = f"""
Extract the following from this WhatsApp job message and return as JSON:
- job_title
- job_description
- company_name
- location
- experience_required
- tech_stack (list)
- contact_info (list of emails or phone numbers)

Message:
\"\"\"{message}\"\"\"

Respond only with valid JSON.
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Remove code block fencing if any
        if text.startswith("```json"):
            text = text.replace("```json", "").strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        print("🔍 Cleaned Output:\n", text)
        job = json.loads(text)
        return job
    except Exception as e:
        print("❌ Error:", e)
        return None

# --------------------------------------
# Score Job Opportunity
# --------------------------------------
def score_job(job):
    score = 0
    tags = []

    desc = job.get("job_description", "").lower()
    title = job.get("job_title", "").lower()
    experience = " ".join(job.get("experience_required", []) if isinstance(job.get("experience_required"), list) else [str(job.get("experience_required", ""))]).lower()
    company = job.get("company_name", "").lower()
    location = job.get("location", "").lower()

    # --- Compensation ---
    if re.search(r"\b(intern|unpaid)\b", desc):
        score += 1
        tags.append("unpaid")
    elif "negotiable" in desc:
        score += 2
        tags.append("negotiable")
    elif re.search(r"\b(inr|lpa|\$|salary|stipend)\b", desc):
        score += 3
        tags.append("well_paid")
        
    # --- Learning ---
    if any(k in desc for k in ["mentorship", "training", "learning", "hands-on"]):
        score += 2
        tags.append("high_learning")
    elif "startup" in desc or "early-stage" in desc:
        score += 1
        tags.append("learning_potential")

    # --- Student Friendly ---
    if re.search(r"\b(intern|fresher|0-1 year|entry level)\b", desc):
        score += 2
        tags.append("student_friendly")
    elif re.search(r"1-2 years", experience):
        score += 1

    # --- Company Reputation ---
    if any(k in company for k in ["google", "microsoft", "amazon", "techcorp", "flipkart"]):
        score += 2
        tags.append("reputed_company")
    elif "startup" in desc:
        score += 1
        tags.append("startup")

    # --- Remote ---
    if any(k in desc + location for k in ["remote", "hybrid", "work from home"]):
        score += 1
        tags.append("remote")

    # --- Full-time / Clear Info ---
    if "full-time" in desc or "permanent" in desc:
        score += 2
        tags.append("full_time")
    elif any(k in desc for k in ["contract", "freelance"]):
        score += 1

    clarity = all(job.get(k) for k in ["job_title", "job_description", "company_name", "location"])
    if clarity and len(desc) > 100:
        score += 2
        tags.append("clear_info")
    elif clarity:
        score += 1

    # Tier
    if score >= 11:
        tier = "high"
    elif score >= 7:
        tier = "medium"
    else:
        tier = "low"

    return {
        "score": score,
        "tier": tier,
        "tags": tags
    }

# --------------------------------------
# Gradio UI Logic
# --------------------------------------
def process_input(message):
    job_info = extract_job_from_text(message)
    if not job_info:
        return "❌ Could not parse the job info.", None

    scored = score_job(job_info)
    job_info.update(scored)

    # Save to file
    with open("scored_jobs.json", "a", encoding="utf-8") as f:
        json.dump(job_info, f, indent=2)
        f.write(",\n")

    return "✅ Job parsed and scored successfully!", json.dumps(job_info, indent=2)

# --------------------------------------
# Gradio App
# --------------------------------------
gr.Interface(
    fn=process_input,
    inputs=gr.Textbox(lines=10, label="Paste WhatsApp Job Message"),
    outputs=[
        gr.Textbox(label="Status"),
        gr.Textbox(label="Parsed & Scored Job (JSON)")
    ],
    title="📩 WhatsApp Job Parser + Scorer",
    description="Uses Gemini 1.5 Flash to extract job details and evaluate opportunity quality.",
).launch(server_port=7863)
