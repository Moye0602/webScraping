from flask import Flask, jsonify
from flask_cors import CORS
import subprocess

app = Flask(__name__)
CORS(app) # This allows your React app to talk to this server

@app.route('/run-scraper', methods=['POST'])
def run_script():
    try:
        # Replace 'scraper.py' with the actual name of your script
        subprocess.run(["python", r"Scripts/wsClearenceJobs.py"], check=True)
        subprocess.run(["python", r"Scripts/atsClearenceJobs.py"], check=True)
        subprocess.run(["python", r"Scripts/sort_llm_results.py"], check=True)
        return jsonify({"status": "success", "message": "Scraper completed!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(port=8000)