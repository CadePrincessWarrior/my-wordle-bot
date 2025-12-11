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

# --- CONFIGURATION ---
WORD_LIST_URL = "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words"
EMAIL_SENDER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASS")
EMAIL_RECEIVER = "YOUR_PHONE_NUMBER@carrier.com" # Change this or use env var

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Crucial for Cloud Run
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def get_word_list():
    response = requests.get(WORD_LIST_URL)
    return response.text.splitlines()

def play_game():
    driver = setup_driver()
    valid_words = get_word_list()
    guesses = []
    
    try:
        print("Starting Wordle...")
        driver.get("https://www.nytimes.com/games/wordle/index.html")
        time.sleep(3)
        
        # Click "Play" or Close Help Modal
        body = driver.find_element(By.TAG_NAME, "body")
        body.click()
        time.sleep(1)
        body.send_keys(Keys.ESCAPE)
        time.sleep(1)

        # Logic: Simple starter word, then random valid words
        # (For a smarter bot, you would filter 'valid_words' based on colors)
        current_guess = "CRANE" # Good starter
        
        for attempt in range(6):
            print(f"Guessing: {current_guess}")
            guesses.append(current_guess)
            
            body.send_keys(current_guess)
            body.send_keys(Keys.ENTER)
            time.sleep(3) 

            # Check if game over (Check for 'Share' button or Modal)
            if "Share" in body.text or "Next Wordle" in body.text:
                print("Game Finished!")
                break
            
            # Simple Bot: Just picks a random word for next guess
            # To make it smart, you must scrape 'aria-label' of tiles here
            current_guess = random.choice(valid_words)
            
        # Capture Result
        result_text = f"Wordle Bot played:\n" + "\n".join(guesses)
        return result_text

    except Exception as e:
        return f"Error occurred: {str(e)}"
    finally:
        driver.quit()

def send_email(body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("No email credentials found. Skipping email.")
        print(body)
        return

    msg = MIMEText(body)
    msg['Subject'] = "Daily Wordle Result"
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    try:
        # Connect to Gmail SMTP (Change if using Outlook/Yahoo)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("Email Sent!")
    except Exception as e:
        print(f"Email Failed: {e}")

if __name__ == "__main__":
    result = play_game()
    send_email(result)