import os
import sys
import subprocess
import json
import time
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from docx import Document

# --- PATH LOGIC ---
# Ensures the script knows where it is relative to the folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# If your resumes are in a folder called 'Resume_Uploads' in the root
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'Resume_Uploads')
APPLIED_TRACKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'applied_jobs.json')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Setup Gemini
api_key = os.getenv("GENAI_API_KEY")
genai.configure(api_key=api_key)

app = Flask(__name__)
CORS(app)

# --- ROUTES ---

# Change the route to a standard API naming convention
@app.route('/api/get-resumes', methods=['GET'])
def get_resumes():
    try:
        # 1. Get the absolute path of the directory server.py is in (Scripts)
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Go UP one level to 'webScraping'
        web_scraping_dir = os.path.dirname(current_script_dir)
        print(web_scraping_dir)
        # 3. Target the Resume folder
        upload_folder = os.path.join(web_scraping_dir, 'Resume_Uploads')
        
        print(f"DEBUG: Looking for resumes in: {upload_folder}")

        if not os.path.exists(upload_folder):
            return jsonify({"error": f"Directory not found: {upload_folder}"}), 404

        files = os.listdir(upload_folder)
        print(f"DEBUG: Found files: {files}")
        resumes = [f for f in files if f.endswith(('.pdf', '.docx', '.txt'))]
        return jsonify({"resumes": resumes})
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-scraper', methods=['POST'])
def run_scraper():
    job_link = request.form.get('link')
    if not job_link:
        return jsonify({"error": "No job link provided"}), 400

    try:
        # Construct the path to the script dynamically
        
        script_path = os.path.join(BASE_DIR, "wsClearenceJobs.py")
        print(script_path)
        print(f"🚀 Starting scraper for: {job_link}")
        subprocess.run([
            sys.executable, 
            script_path, 
            "--link", job_link
        ], check=True)
        
        return jsonify({"status": "success", "message": "Scraping complete!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-ats', methods=['POST'])
def run_ats():
    resume_filename = request.form.get('resume_name')
    model_choice = request.form.get('model')

    if not resume_filename:
        return jsonify({"error": "No resume selected"}), 400

    resume_path = os.path.join(UPLOAD_FOLDER, resume_filename)

    try:
        script_path = os.path.join(BASE_DIR, "atsClearenceJobs.py")
        
        subprocess.run([
            sys.executable,
            script_path,
            "--resume_path", resume_path,
            "--model", model_choice
        ], check=True)
        
        return jsonify({"status": "success", "message": f"ATS Analysis complete for {resume_filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-models', methods=['GET'])
def get_models():
    """Fetches and categorizes Gemini models."""
    try:
        raw_models = genai.list_models()
        selectable = []
        for m in raw_models:
            if 'generateContent' in m.supported_generation_methods:
                selectable.append({
                    "name": m.name,
                    "display_name": m.display_name,
                    "tier": "PAID" if "pro" in m.name else "FREE"
                })
        return jsonify({'models': selectable})
    except Exception as e:
        return jsonify({"error": str(e)}), 500





@app.route('/api/mark-applied', methods=['POST'])
def mark_applied():
    """Endpoint for React to signal that a job has been applied to."""
    def get_applied_ids():
        """Reads the list of applied job IDs from the JSON tracker."""
        if not os.path.exists(APPLIED_TRACKER_PATH):
            return []
        try:
            with open(APPLIED_TRACKER_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    data = request.json
    job_id = data.get('jobId')
    
    if not job_id:
        return jsonify({"error": "No jobId provided"}), 400

    applied_ids = get_applied_ids()
    if job_id not in applied_ids:
        applied_ids.append(job_id)
        with open(APPLIED_TRACKER_PATH, 'w') as f:
            json.dump(applied_ids, f, indent=4)
    
    return jsonify({"status": "success", "applied": applied_ids})

@app.route('/api/tailor-resume', methods=['POST'])
def handle_tailoring():
    import resumeWriter
    data = request.json
    print(data)
    job_id = data.get('jobId')
    resume_name = data.get('resume_name')
    def extract_text_from_docx(file_path):
        try:
            doc = Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            return "\n".join(full_text)
        except Exception as e:
            print(f"Error reading Word doc: {e}")
            return ""

    try:
        # 1. Locate Master Analysis (Moving up from Scripts to src)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        analysis_path = os.path.join(f'{base_dir}\\JobData\\ClearanceJobs', 'MASTER_ANALYSIS.json')
        with open(analysis_path, 'r') as f:
            all_jobs = json.load(f)
        
        # 2. Extract the specific job data
        target_job = next((j for j in all_jobs if j.get('jobId') == job_id), None)
        if not target_job:
            return jsonify({"error": "Job details not found for tailoring."}), 404

        # 3. Read Master Resume Text (Assumes you have a helper to get text)
        resume_path = os.path.join(base_dir, 'Resume_Uploads_', resume_name)
        master_text = extract_text_from_docx(resume_path) # You'll need a PDF/Docx parser here

        # 4. Invoke the Tailor Logic
        tailored_content = resumeWriter.invoke_gemini_tailor(master_text, target_job)
        
        return jsonify({
            "status": "success",
            "data": tailored_content
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

##########################################
if __name__ == "__main__":
    app.run(port=8000, debug=True)