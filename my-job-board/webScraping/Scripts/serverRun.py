import subprocess
import time
import os
import sys

def launch():
    # 1. Start the Flask Backend
    print("🚀 Starting Python Backend (Flask)...")
    # Use 'sys.executable' to ensure it uses the same python that runs this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(current_dir, "server.py")
    backend = subprocess.Popen([sys.executable, server_path], cwd=current_dir)

    # 2. Wait a moment for the backend to initialize
    time.sleep(2)

    # 3. Start the React Frontend
    print("⚛️  Starting React Frontend (Vite)...")
    project_dir = os.path.join(os.getcwd(), "my-job-board")
    
    # 'shell=True' is necessary on Windows for npm
    frontend = subprocess.Popen("npm run dev", shell=True, cwd=project_dir)

    try:
        # Keep the script alive while both processes run
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\nTerminating servers...")
        backend.terminate()
        frontend.terminate()

if __name__ == "__main__":
    launch()