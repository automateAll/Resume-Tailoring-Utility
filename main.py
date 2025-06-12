from utils.resume_utils import (
    load_resume_json,
    check_resume_compatibility_using_llm,
    render_resume_to_pdf, extract_updated_resume_sections
)
base_resume_path = "resources/resume_structured.json"
job_description_path = "resources/jd_input.txt"
template_path = "resources/resume_template.html"
output_path = "output/final_resume.pdf"

def main():
    resume_data = load_resume_json(base_resume_path)
    ai_enhanced_partial_resume = check_resume_compatibility_using_llm(job_description_path,resume_data)
    final_resume = extract_updated_resume_sections(ai_enhanced_partial_resume,resume_data)
    # print("UPDATED RESUME.............")
    # print(final_resume)
    # render_resume_to_pdf(final_resume, template_path, output_path)

if __name__ == "__main__":
    main()