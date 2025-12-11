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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# --- CONFIGURATION & GLOBALS ---
# Source for a reliable list of Wordle solution words
WORD_LIST_URL = "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words"

# Credentials pulled securely from GitHub Secrets (EMAIL_USER, EMAIL_PASS)
EMAIL_SENDER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASS")

# !!! IMPORTANT: REPLACE THIS with your receiving email or phone number !!!
# e.g., "myphone@vtext.com" (for Verizon) or "myemail@gmail.com"
EMAIL_RECEIVER = "YOUR_TARGET_EMAIL_OR_PHONE@CARRIER.COM" 


# --- CORE LOGIC FUNCTIONS (The "Brain") ---

def filter_words(word_list, last_guess, feedback):
    """Filters the list of potential solution words based on the feedback."""
    new_list = []
    
    for word in word_list:
        is_valid = True
        
        for i, (letter, result) in enumerate(zip(last_guess, feedback)):
            
            # 1. ABSENT (Gray): Letter is not in the solution.
            if result == 'absent':
                # Skip if the letter is in the potential word, UNLESS 
                # that letter was also marked 'present' or 'correct' elsewhere 
                # (meaning there's a duplicate, which is complex and often skipped 
                # by simple solvers. We use a simple check here.)
                if letter in word and word.count(letter) <= last_guess.count(letter):
                    is_valid = False
                    break

            # 2. PRESENT (Yellow): Letter is in the word, but not at this position.
            elif result == 'present':
                # Word MUST contain the letter
                if letter not in word:
                    is_valid = False
                    break
                # Word MUST NOT have the letter at this specific position
                if word[i] == letter:
                    is_valid = False
                    break

            # 3. CORRECT (Green): Letter is in the word and in the right position.
            elif result == 'correct':
                # Word MUST have this letter at this specific position
                if word[i] != letter:
                    is_valid = False
                    break

        if is_valid:
            new_list.append(word)
            
    return new_list

def get_next_guess(attempt, valid_words):
    """Picks the next word to guess based on the current state."""
    if attempt == 0:
        return "CRANE" # Statistically strong starter
    
    # After the first guess, pick a random word from the remaining possibilities
    if valid_words:
        return random.choice(valid_words)
    
    # Fallback if no valid words remain
    return "LUCKY" 


# --- BROWSER AUTOMATION FUNCTIONS (The "Hands") ---

def setup_driver():
    """Configures and starts the Chrome web driver for cloud execution."""
    chrome_options = Options()
    
    # Essential for cloud hosting and bypassing simple bot detection
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Use a standard user-agent string to mimic a real browser
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def get_word_list():
    """Downloads the list of valid words from GitHub."""
    try:
        response = requests.get(WORD_LIST_URL)
        response.raise_for_status() # Raise an exception for bad status codes
        return [word.upper() for word in response.text.splitlines() if len(word) == 5]
    except Exception as e:
        print(f"Error downloading word list: {e}")
        # Fallback to a hardcoded minimal list if download fails
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
        
        # Access the Shadow DOM root for the game
        game_app = driver.find_element(By.TAG_NAME, 'game-app')
        shadow_root_1 = driver.execute_script("return arguments[0].shadowRoot", game_app)
        
        # Access the game board root
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

            # 2. Read the Board State for the current row
            try:
                row = shadow_root_2.find_elements(By.TAG_NAME, 'game-row')[attempt]
                row_shadow = driver.execute_script("return arguments[0].shadowRoot", row)
                tiles = row_shadow.find_elements(By.TAG_NAME, 'game-tile')
            except Exception as e:
                # This often happens if the game is already over (win/loss modal)
                print(f"Could not read row {attempt}: {e}")
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
            
            # Filter the word list for the next loop
            valid_words = filter_words(valid_words, current_guess, current_feedback)

        # If the loop finishes without a win:
        return f"Wordle Bot LOST (6/6).\n\nGuesses:\n" + "\n".join(feedback_history)

    except Exception as e:
        print(f"Critical error during gameplay: {e}")
        return f"Wordle Bot FAILED with critical error: {str(e)}"
    finally:
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
        # Connect to Gmail SMTP (Change to your provider's SMTP server if needed)
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
