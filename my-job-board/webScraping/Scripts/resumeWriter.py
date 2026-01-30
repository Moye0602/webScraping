import google.generativeai as genai
import os,json
from profileSettings import llmModel
api_key = os.getenv("GENAI_API_KEY")
genai.configure(api_key=api_key)

def invoke_gemini_tailor(resume_text, job_data, model_name):
    model = genai.GenerativeModel(llmModel)
    
    prompt = f"""
    Act as a professional Executive Resume Writer specializing in Defense and Aerospace.
    
    JOB TITLE: {job_data.get('role_name')}
    DESCRIPTION: {job_data.get('full_description')}
    
    MY MASTER RESUME TEXT:
    {resume_text}
    
    TASK:
    1. Rewrite the 'Professional Summary' to perfectly align with this specific role.
    2. Identify the top 3 requirements in the job description and rewrite 3 bullet points from my experience to mirror those specific technical terms (e.g., JCIDS, RMF, specific agencies).
    3. Keep all factual dates and titles identical.
    
    OUTPUT FORMAT:
    Return ONLY a JSON object with these keys:
    {{
        "tailored_summary": "string",
        "tailored_bullets": ["bullet1", "bullet2", "bullet3"],
        "explanation": "one sentence on the strategy used"
    }}
    """
     
    try:
        response = model.generate_content(prompt)
        # Clean the response text for JSON parsing
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        return {"error": f"LLM Tailoring failed: {str(e)}"}