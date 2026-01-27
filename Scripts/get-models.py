import json,os
import google.generativeai as genai
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from common.helper import cprint

# Setup API Key
api_key = os.getenv("GENAI_API_KEY")
genai.configure(api_key=api_key)

def get_model_selection():
    """
    Lists Gemini models sorted by Free Tier availability first, 
    then Paid-only models.
    """
    try:
        raw_models = genai.list_models()
        
        # Define known "Paid Only" models based on 2026 status
        # Note: gemini-3-pro and specialized 'image' variants usually require billing.
        paid_keywords = ["-3-pro", "image", "ultra", "vision"]
        
        free_tier = []
        paid_tier = []

        for m in raw_models:
            if 'generateContent' in m.supported_generation_methods:
                model_data = {"display_name": m.display_name, "name": m.name}
                
                # Sort logic: check if name contains any paid keywords
                if any(key in m.name.lower() for key in paid_keywords):
                    paid_tier.append(model_data)
                else:
                    free_tier.append(model_data)

        # Combine lists: Free first, then Paid
        all_selectable = free_tier + paid_tier
        
        print("\n--- Available Gemini Models ---")
        print(f"{'#':<3} {'Model Name':<30} {'Tier Access'}")
        print("-" * 50)

        for i, m in enumerate(all_selectable, 1):
            # Labeling the tier for clarity
            is_free = i <= len(free_tier)
            tier_label = "[FREE TIER]" if is_free else "[PAID ONLY]"
            
            # Highlight Flash-Lite or Flash as recommended for your scraper
            rec = " ⭐" if "flash" in m['display_name'].lower() and is_free else ""
            
            print(f"{i:<3} {m['display_name']:<30} {tier_label}{rec}")

        # User Input Logic
        while True:
            try:
                msg = f"\nSelect model (1-{len(all_selectable)}) [Default: 1]: "
                choice = input(msg).strip()
                
                if choice == "":
                    selected = all_selectable[0]
                    break
                    
                idx = int(choice)
                if 1 <= idx <= len(all_selectable):
                    selected = all_selectable[idx - 1]
                    break
                print("Out of range.")
            except ValueError:
                print("Enter a valid number.")

        print(f"✅ Active Model: {selected['display_name']}")
        return selected['name']

    except Exception as e:
        print(f"❌ Error: {e}")
        return None
# --- Example Usage ---
# MODEL_ID = get_model_selection()
# model = genai.GenerativeModel(MODEL_ID)

# # Store models as JSON
# with open("available_models.json", "w") as f:
#     json.dump(models_list, f, indent=2)
get_model_selection()
