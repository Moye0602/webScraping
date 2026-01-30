import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import sys
import google.generativeai as genai
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Setup API Key
api_key = os.getenv("GENAI_API_KEY")
genai.configure(api_key=api_key)
app = Flask(__name__)
CORS(app)

# Configuration for file storage
UPLOAD_FOLDER = 'Resume_Uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/run-scraper', methods=['POST'])
def run_scraper():
    # Use request.form because React is sending FormData
    # 1. Get the filename from the dropdown selection
    job_link = request.form.get('link')

    # Basic Validation
    if not job_link:
        return jsonify({"error": "No job link provided"}), 400

    # 2. Build the absolute path to the existing file
    # We assume the file is already inside your UPLOAD_FOLDER

    # Safety check: Does the file actually exist on the server?

    try:
        # 3. Run the Subprocess Chain
        # We pass the existing resume_path to the scraper
        print(f"🚀 Starting web scraping for Clearance Jobs")
        
        subprocess.run([
            sys.executable, 
            r"Scripts/wsClearenceJobs.py", 
            "--link", job_link, 

        ], check=True)


        
        return jsonify({
            "status": "success", 
            "message": f"Analysis complete for Clearance Jobs!"
        })

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Script execution failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/run-ats', methods=['POST'])
def run_ats():
    # Use request.form because React is sending FormData
    # 1. Get the filename from the dropdown selection
    resume_filename = request.form.get('resume_name')
    model_choice = request.form.get('model')

    # Basic Validation
    if not resume_filename:
        return jsonify({"error": "No resume selected from the list"}), 400

    # 2. Build the absolute path to the existing file
    # We assume the file is already inside your UPLOAD_FOLDER
    resume_path = os.path.join(UPLOAD_FOLDER, resume_filename)

    # Safety check: Does the file actually exist on the server?
    if not os.path.exists(resume_path):
        return jsonify({"error": f"File {resume_filename} not found on server"}), 404

    try:
        # 3. Run the Subprocess Chain
        # We pass the existing resume_path to the scraper
        print(f"🚀 Starting analysis: {resume_filename} using {model_choice}")
    # Run subsequent processing scripts
        subprocess.run([sys.executable,
                         r"Scripts/atsClearenceJobs.py",
                        "--resume_path", resume_path,
                        "--model", model_choice],
                          check=True)
        # subprocess.run([sys.executable, r"Scripts/sort_llm_results.py"], check=True)
       
        return jsonify({
            "status": "success", 
            "message": f"Analysis complete for {resume_filename}!"
        })
        

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Script execution failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/get-Models', methods=['GET'])
def getModels():
    """
    Fetches Gemini models and returns a categorized list to the React UI.
    """
    try:
        raw_models = genai.list_models()
        
        # Define known "Paid Only" models based on 2026 status
        paid_keywords = ["-3-pro", "image", "ultra", "vision"]
        
        free_tier = []
        paid_tier = []

        for m in raw_models:
            if 'generateContent' in m.supported_generation_methods:
                # Determine tier and recommendation
                is_paid = any(key in m.name.lower() for key in paid_keywords)
                is_flash = "flash" in m.display_name.lower()
                
                model_data = {
                    "name": m.name,
                    "display_name": f"{'⭐ ' if is_flash and not is_paid else ''}{m.display_name}",
                    "tier": "FREE TIER" if not is_paid else "PAID ONLY"
                }
                
                if is_paid:
                    paid_tier.append(model_data)
                else:
                    free_tier.append(model_data)

        # Combine: Free first, then Paid
        all_selectable = free_tier + paid_tier
        
        # Return as JSON to React
        return jsonify({'models': all_selectable})

    except Exception as e:
        # It's better to return a 500 error if the API call fails
        return jsonify({"error": str(e)}), 500
    
import os
from flask import Flask, request, jsonify
# ... your other imports

@app.route('.webScraping/Scripts/get-resumes', methods=['GET'])
def get_resumes():
    try:
        # List all files in the Resume_Uploads directory
        files = os.listdir(UPLOAD_FOLDER)
        # Filter for common resume extensions
        resumes = [f for f in files if f.endswith(('.pdf', '.docx', '.txt'))]
        return jsonify({"resumes": resumes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload-resume', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['resume']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    return jsonify({"message": "Upload successful", "filename": file.filename})


if __name__ == "__main__":
    app.run(port=8000, debug=True)
    # print(getModels())