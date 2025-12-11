import time
import smtplib
import random
import requests
import os
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
# Removed: from webdriver_manager.chrome import ChromeDriverManager 
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC 

# --- CONFIGURATION & GLOBALS ---
WORD_LIST_URL = "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words"

EMAIL_SENDER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASS")

# !!! IMPORTANT: REPLACE THIS with your receiving email or phone number !!!
EMAIL_RECEIVER = "YOUR_TARGET_EMAIL_OR_PHONE@CARRIER.COM" 


# --- CORE LOGIC FUNCTIONS (The "Brain") ---

def filter_words(word_list, last_guess, feedback):
    """Filters the list of potential solution words based on the feedback."""
    new_list = []
    
    for word in word_list:
        is_valid = True
        
        for i, (letter, result) in enumerate(zip(last_guess, feedback)):
            
            # 1. ABSENT (Gray)
            if result == 'absent':
                if letter in word and word.count(letter) <= last_guess.count(letter):
                    is_valid = False
                    break

            # 2. PRESENT (Yellow)
            elif result == 'present':
                if letter not in word:
                    is_valid = False
                    break
                if word[i] == letter:
                    is_valid = False
                    break

            # 3. CORRECT (Green)
            elif result == 'correct':
                if word[i] != letter:
                    is_valid = False
                    break

        if is_valid:
            new_list.append(word)
            
    return new_list

def get_next_guess(attempt, valid_words):
    if attempt == 0:
        return "CRANE" 
    if valid_words:
        return random.choice(valid_words)
    return "LUCKY" 


# --- BROWSER AUTOMATION FUNCTIONS (The "Hands") ---

def setup_driver():
    """Configures and starts the Chrome web driver using the manual installation path."""
    chrome_options = Options()
    
    # Core stability and headless mode
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Advanced Stability and Crash Avoidance Flags
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--incognito") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")
    
    # --- MANUAL DRIVER PATH (FIX for webdriver-manager crash) ---
    # On Ubuntu, the default path for the driver installed with Chrome is /usr/bin/chromedriver
    service = Service("/usr/bin/chromedriver")
    # -----------------------------------------------------------
    
    return webdriver.Chrome(service=service, options=chrome_options)

# ... (get_word_list, play_game, send_email, and __main__ functions remain the same) ...
# NOTE: The rest of the file below is exactly the same as the previous version
# to maintain all other logic, but has been truncated here for brevity. 


def get_word_list():
    """Downloads the list of valid words from GitHub."""
    try:
        response = requests.get(WORD_LIST_URL)
        response.raise_for_status() 
        return [word.upper() for word in response.text.splitlines() if len(word) == 5]
    except Exception as e:
        print(f"Error downloading word list: {e}")
        return ["CRANE", "ADEPT", "ROAST", "SLICE", "FLOCK", "GRIME"]


def play_game():
    """Main function to run the Wordle game loop."""
    driver = setup_driver()
    valid_words = get_word_list()
    feedback_history = []
    
    try:
        print("Starting Wordle...")
        driver.get("https://www.nytimes.com/games/wordle/index.html")
        time.sleep(3)
        
        # 1. Handle "Play" and Close Help Modal
        body = driver.find_element(By.TAG_NAME, "body")
        body.click()
        time.sleep(1)
        body.send_keys(Keys.ESCAPE)
        time.sleep(1)
        
        # 2. Wait for the main game element to be present (FIXED "NO SUCH ELEMENT" CRASH)
        print("Waiting for game board...")
        wait = WebDriverWait(driver, 10)
        game_app = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'game-app')))
        
        # 3. Access the Shadow DOM roots and game board
        shadow_root_1 = driver.execute_script("return arguments[0].shadowRoot", game_app)
        game_board = shadow_root_1.find_element(By.TAG_NAME, 'game-board')
        shadow_root_2 = driver.execute_script("return arguments[0].shadowRoot", game_board)
        
        for attempt in range(6):
            if not valid_words:
                print("Bot failed: No valid words remaining.")
                break
                
            current_guess = get_next_guess(attempt, valid_words)
            print(f"Attempt {attempt + 1}: Guessing {current_guess}")
            
            body.send_keys(current_guess)
            body.send_keys(Keys.ENTER)
            time.sleep(3) 

            # 4. Read the Board State for the current row
            try:
                row = shadow_root_2.find_elements(By.TAG_NAME, 'game-row')[attempt]
                row_shadow = driver.execute_script("return arguments[0].shadowRoot", row)
                tiles = row_shadow.find_elements(By.TAG_NAME, 'game-tile')
            except Exception as e:
                print(f"Could not read row {attempt}, game may be over: {e}")
                break

            current_feedback = []
            win = True
            for tile in tiles:
                evaluation = tile.get_attribute('evaluation')
                current_feedback.append(evaluation)
                if evaluation != 'correct':
                    win = False
            
            # Format the feedback into an emoji grid line for the email
            emoji_feedback = "".join([
                "🟩" if f == 'correct' else 
                "🟨" if f == 'present' else 
                "⬛" for f in current_feedback
            ])
            feedback_history.append(f"{current_guess} ({emoji_feedback})")
            
            if win:
                print("WIN!")
                return f"Wordle Bot WON in {attempt + 1}/6 attempts!\n\n{emoji_feedback}\n\nGuesses:\n" + "\n".join(feedback_history)
            
            # 5. Filter the word list for the next loop
            valid_words = filter_words(valid_words, current_guess, current_feedback)

        # If the loop finishes without a win:
        return f"Wordle Bot LOST (6/6).\n\nGuesses:\n" + "\n".join(feedback_history)

    except Exception as e:
        print(f"Critical error during gameplay: {e}")
        return f"Wordle Bot FAILED with critical error: {str(e)}"
    finally:
        # Crucial step: Ensure the browser is closed to free up resources
        driver.quit()


# --- NOTIFICATION FUNCTIONS (The "Messenger") ---

def send_email(subject, body):
    """Sends the result via email using SMTP."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("ERROR: Email credentials not found in environment. Skipping email.")
        print("Final Result:\n", body)
        return

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    try:
        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"Email Sent successfully to {EMAIL_RECEIVER}!")
    except Exception as e:
        print(f"Email Failed: {e}")


# --- EXECUTION ---

if __name__ == "__main__":
    subject = "Daily Wordle Bot Run"
    result = play_game()
    
    # Extract win/loss status for subject line
    if "WON" in result:
        subject = "✅ Wordle Bot SUCCESS!"
    elif "LOST" in result:
        subject = "❌ Wordle Bot LOST."
    elif "FAILED" in result:
        subject = "🚨 Wordle Bot CRASHED."
        
    send_email(subject, result)
