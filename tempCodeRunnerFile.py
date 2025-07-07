import gradio as gr
import google.generativeai as genai
import json
import os
import subprocess
import re
from PIL import Image
import pytesseract

# --------------------------------------
# Gemini Flash Setup
# --------------------------------------
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise EnvironmentError("Please set GOOGLE_API_KEY environment variable.")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# --------------------------------------
# Job Extraction Prompt
# --------------------------------------
def process_job_with_llm(message):
    prompt = f"""
You are an intelligent job evaluator. Given a WhatsApp message about a job opportunity, your task is to:

1. Extract job information.
2. If the tech stack is not explicitly mentioned, infer a relevant tech stack from the job description.
3. Score the job based on the following criteria.
4. Assign relevant tags.
5. Return everything as valid JSON.

--- Extract the following fields ---
- job_title
- job_description
- company_name
- location
- experience_required
- tech_stack (list)
- contact_info (list of emails and phone numbers)

--- Evaluate and return ---
- score (0 to 15)
- tier: "high", "medium", "low"
- tags (list): choose from ["unpaid", "well_paid", "negotiable", "student_friendly", "high_learning", "reputed_company", "startup", "remote", "full_time", "clear_info"]

--- Scoring Guidelines ---
- Compensation:
    - unpaid/intern → +1
    - negotiable → +2
    - stipend/salary/inr/lpa → +3
- Learning opportunity (training, mentorship, hands-on): +1 to +2
- Student friendly (0-1 yr, fresher, intern): +1 to +2
- Remote/hybrid/work from home: +1
- Reputed company (Google, Microsoft, Amazon, Flipkart): +2
- Full-time or clear job info: +1 to +2

Respond only with valid JSON. Use this job message:

\"\"\"{message}\"\"\"
"""
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        print("🧠 Raw Gemini output:\n", result)

        # Clean code block markers
        result = result.replace("```json", "").replace("```", "").strip()

        # Find both JSON parts using a regex (2 objects back-to-back)
        matches = re.findall(r"\{[^{}]+\}", result, re.DOTALL)

        if len(matches) == 2:
            # Merge them
            job_data = json.loads(matches[0])
            score_data = json.loads(matches[1])
            job_data.update(score_data)
            return job_data
        else:
            # fallback: try to load whole thing as one object
            json_start = result.find("{")
            if json_start != -1:
                result = result[json_start:]
            return json.loads(result)

    except Exception as e:
        print("❌ Error parsing JSON:", e)
        return None

# --------------------------------------
# OCR from Image
# --------------------------------------
def extract_text_from_image(image: Image.Image):
    text = pytesseract.image_to_string(image)
    return text.strip()
   
# --------------------------------------
# Combined Input Processor
# --------------------------------------
def process_input(text_message, image):
    message = text_message.strip()
    if not message and image is not None:
        message = extract_text_from_image(image)

    if not message:
        return "❌ No input text or image provided.", None

    # Detect LinkedIn job URL
    linkedin_url_match = re.search(r"https://www\.linkedin\.com/jobs/view/\d+", message)
    if linkedin_url_match:
        linkedin_url = linkedin_url_match.group(0)
        try:
            result = subprocess.run(
                ["node", "linkedinscrap.js", linkedin_url],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return f"❌ Scraper failed: {result.stderr}", None
            scraped_data = json.loads(result.stdout.strip())
            message = json.dumps(scraped_data, indent=2)
        except Exception as e:
            return f"❌ Error running scraper: {str(e)}", None

    # Process job text (original or scraped) with LLM
    print("🔍 Message sent to LLM:\n", message)
    job_info = process_job_with_llm(message)
    if not job_info:
        return "❌ Could not parse job info.", None

    # Save to file
    with open("scored_jobs.json", "a", encoding="utf-8") as f:
        json.dump(job_info, f, indent=2)
        f.write(",\n")

    return "✅ Job parsed and scored successfully!", json.dumps(job_info, indent=2)

# --------------------------------------
# Gradio App UI
# --------------------------------------
gr.Interface(
    fn=process_input,
    inputs=[
        gr.Textbox(lines=8, label="Paste WhatsApp Job Message or LinkedIn URL (Optional)"),
        gr.Image(type="pil", label="Or Upload Job Image (Optional)")
    ],
    outputs=[
        gr.Textbox(label="Status"),
        gr.Textbox(label="Parsed & Scored Job (JSON)")
    ],
    title="📩 Job Parser + Scorer (LLM + Puppeteer)",
    description="Upload a screenshot, paste a message, or share a LinkedIn job link. We'll extract, score, and tag it using Gemini 1.5 Flash.",
).launch(server_port=7872)
