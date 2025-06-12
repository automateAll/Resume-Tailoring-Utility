import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI
import ast
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from PyPDF2 import PdfReader

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

def load_resume_json(file_path):
    print("Loading base resume to compare")
    with open(file_path, 'r', encoding='utf-8') as f:
        resume_data = json.load(f)
        return resume_data

def check_resume_compatibility_using_llm(job_description_path,resume_data):
    print("extract_keywords_from_jd")
    with open(job_description_path , 'r', encoding='utf-8') as f:
        job_description_text = f.read()

    prompt = f"""
Can you check if the given job description aligns with the resume, and suggest modifications to improve the alignment?

Please follow these strict guidelines:
- Keep the resume concise and aligned with the job description.
- Eliminate or summarize content that is not directly relevant to the job.
- Ensure the final resume content would fit within **2 pages** when rendered as PDF (A4 size, 10pt font, minimal spacing).
- Return **only** the modified fields in the form of a **valid Python-style dictionary**, wrapped inside a ```json code block.
- Use the **Python keyword `Ellipsis`** for any fields that are unchanged (not "...", not "...(unchanged)", not `{ ... }`).
- Make sure the output is syntactically correct and **parsable using `ast.literal_eval()`**.
- Do not nest unrelated keys (e.g., avoid putting "Cloud & DevOps" inside "Frameworks & Tools").
- Avoid trailing commas or syntax errors.
- Do not include 'Ellipsis' as a key. Only use it as a value in place of unchanged fields.
- Please begin the response with ```json and end with ```. Use valid Python dictionary syntax parsable by ast.literal_eval(), and do not use ... in string format. Use the actual Python keyword Ellipsis for unchanged fields.

    Here is the Job Description:
    {job_description_text}
    
    Here is the Resume:
    {resume_data}
    """
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    llm_response = response.choices[0].message.content
    print("llm_response: ",llm_response)
    return llm_response


def extract_updated_resume_sections(ai_enhanced_partial_resume,resume_data):
    """
    Extracts updated sections (like summary, skills, experience, projects) from LLM output.
    Assumes the LLM returned partial JSON-like strings.
    """
    updated_resume = {}

    # Step 1: Extract JSON block using regex
    extract_json_block(ai_enhanced_partial_resume)

    print("updated_resume: ",updated_resume)
    update_version = merge_resume_with_original(updated_resume,resume_data)
    return update_version

def extract_json_block(text):
    # Match any code block that looks like a Python dict
    match = re.search(r"```(?:json)?\s*({.*?})\s*```", text, re.DOTALL)
    if not match:
        # Try fallback if no backticks were used (just extract first large curly block)
        match = re.search(r"({.*})", text, re.DOTALL)

    if match:
        try:
            return ast.literal_eval(match.group(1))
        except Exception as e:
            print("⚠️ Failed to parse block:", e)
            return {}
    else:
        print("⚠️ No valid Python-style dictionary found in response.")
        return {}


def convert_ellipsis(obj):
    if isinstance(obj, str) and obj.strip() == "...":
        return Ellipsis
    elif isinstance(obj, list):
        return [convert_ellipsis(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_ellipsis(v) for k, v in obj.items()}
    else:
        return obj

def merge_resume_with_original(updated, original):
    """
    Merges updated resume into the original.
    - Preserves all fields from the original unless explicitly updated.
    - Replaces fields in the updated version (unless value is Ellipsis).
    """
    print("Merging with original resume")
    final_resume = original.copy()

    for key, value in updated.items():
        if value is Ellipsis:
            continue  # Skip placeholders
        elif isinstance(value, dict) and isinstance(original.get(key), dict):
            final_resume[key] = original[key].copy()
            final_resume[key].update(value)
        else:
            final_resume[key] = value

    auto_trim_resume_to_two_pages(final_resume,
                                "resources/resume_template.html",
                                  "output/final_resume.pdf")
    return final_resume

def render_resume_to_pdf(final_resume, template_path, output_path):
    print("Generating PDF")
    # Setup Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(os.path.dirname(template_path))
    )
    template = env.get_template(os.path.basename(template_path))

    # Render HTML with the resume data
    rendered_html = template.render(**final_resume)

    # Convert to PDF
    HTML(string=rendered_html).write_pdf(output_path)
    print(f"✅ Resume PDF generated at: {output_path}")

def auto_trim_resume_to_two_pages(final_resume, template_path, output_path, max_attempts=3):
    attempt = 0
    while attempt < max_attempts:
        render_resume_to_pdf(final_resume, template_path, output_path)
        page_count = get_pdf_page_count(output_path)
        if page_count <= 2:
            print("✅ PDF fits within 2 pages.")
            return
        else:
            print(f"⚠️ PDF has {page_count} pages. Requesting LLM to trim content to 2 pages...")

            prompt = f"""
You previously suggested changes to align this resume with a job description.

However, the rendered resume still exceeds 2 pages.

Please re-trim or summarize the content further (especially long responsibilities, projects, and skills) to ensure the final PDF fits within **2 pages max** (A4, 10pt font, tight spacing). Respond in JSON format and use Ellipsis (...) for unchanged sections.

Resume:
{final_resume}
"""
            response = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            llm_response = response.choices[0].message.content
            updated_resume = extract_updated_resume_sections(llm_response, final_resume)
            resume_data = updated_resume
            attempt += 1

    print("⚠️ Max trimming attempts reached. Resume still exceeds 2 pages.")


def get_pdf_page_count(pdf_path):
    reader = PdfReader(pdf_path)
    print(len(reader.pages))
    return len(reader.pages)
