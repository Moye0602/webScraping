import os
import sys
import subprocess
import json
import time
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS

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
        # We need to go UP two levels from 'Scripts' to find 'Resume_Uploads_'
        # Scripts -> webScraping -> Resume_Uploads_
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_folder = os.path.join(base_path, 'Resume_Uploads_')
        
        files = os.listdir(upload_folder)
        resumes = [f for f in files if f.endswith(('.pdf', '.docx', '.txt'))]
        return jsonify({"resumes": resumes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-scraper', methods=['POST'])
def run_scraper():
    job_link = request.form.get('link')
    if not job_link:
        return jsonify({"error": "No job link provided"}), 400

    try:
        # Construct the path to the script dynamically
        script_path = os.path.join(BASE_DIR, "Scripts", "wsClearenceJobs.py")
        
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
        script_path = os.path.join(BASE_DIR, "Scripts", "atsClearenceJobs.py")
        
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



def get_applied_ids():
    """Reads the list of applied job IDs from the JSON tracker."""
    if not os.path.exists(APPLIED_TRACKER_PATH):
        return []
    try:
        with open(APPLIED_TRACKER_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return []

@app.route('/api/mark-applied', methods=['POST'])
def mark_applied():
    """Endpoint for React to signal that a job has been applied to."""
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

##########################################
if __name__ == "__main__":
    app.run(port=8000, debug=True)