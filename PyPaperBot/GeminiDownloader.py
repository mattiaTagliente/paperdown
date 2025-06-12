# PyPaperBot/GeminiDownloader.py
from google import genai
from selenium.webdriver.common.by import By
from .NetInfo import NetInfo
import time
import json

def get_agent_action(driver, paper_obj, instruction):
    """
    Takes a screenshot and asks the Gemini model for the next action.
    """
    print(f"    Gemini Agent: {instruction}")
    try:
        # FIX: Use modern genai SDK initialization and call
        if not NetInfo.gemini_api_key:
             raise ValueError("Gemini API key not found in NetInfo.")
        genai.configure(api_key=NetInfo.gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        screenshot_base64 = driver.get_screenshot_as_base64()
        screenshot_part = {
            "mime_type": "image/png",
            "data": screenshot_base64
        }
        
        prompt = f"""
        You are an expert web automation agent. Your task is to download a PDF of a research paper titled "{paper_obj.title}".
        Analyze the provided screenshot and instruction. Respond with a JSON object for the next action.
        Possible actions: "CLICK", "DOWNLOAD_COMPLETE", "FAIL".
        If action is CLICK, provide the "xpath" for the element to click.
        Example: {{"action": "CLICK", "xpath": "//a[@id='pdf-button']"}}
        Instruction: "{instruction}"
        """
        
        response = model.generate_content([prompt, screenshot_part])
        
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        action_json = json.loads(cleaned_response)
        
        print(f"    Gemini Agent suggests: {action_json}")
        return action_json

    except Exception as e:
        print(f"    Gemini Agent failed to get action. Reason: {e}")
        return {"action": "FAIL", "reason": str(e)}

def download_with_gemini_agent(driver, paper_obj):
    """
    Uses a Gemini-powered agent to navigate and download a PDF.
    """
    instruction = "Find and click the primary link or button to access the PDF."
    for step in range(5):
        print(f"\n-- Gemini Agent Step {step + 1}/5 --")
        action_json = get_agent_action(driver, paper_obj, instruction)
        
        action = action_json.get("action")
        
        if action == "CLICK":
            try:
                element = driver.find_element(By.XPATH, action_json["xpath"])
                driver.execute_script("arguments[0].click();", element)
                instruction = "I have clicked the element. What is the next step?"
                time.sleep(5)
            except Exception as e:
                instruction = f"Clicking the XPath failed: {e}. Please find a new element to click."
        
        elif action == "DOWNLOAD_COMPLETE":
            print("    Gemini Agent confirms download should be complete.")
            return True

        elif action == "FAIL":
            print(f"    Gemini Agent failed: {action_json.get('reason')}")
            return False
            
        else:
            instruction = "Invalid action. Please re-evaluate the page."

    print("    Gemini Agent reached max steps.")
    return False