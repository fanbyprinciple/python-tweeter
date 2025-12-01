import re
import yaml
import os
import logging
import time
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
import tweepy
from dotenv import load_dotenv

# --- Configuration & Setup ---
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Constants
PROCESSED_FILE = "processed_videos.txt"
TWEETS_FILE = "tweets.yaml"
# Max characters of transcript to feed to the LLM (Good for cost control)
MAX_TRANSCRIPT_CHARS = 15000 

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "x-ai/grok-4.1-fast:free" 

# Initialize Clients
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)
# Initialize the YouTube Transcript Client
YTT_CLIENT = YouTubeTranscriptApi() 

# --- Utility Functions ---

def load_processed_videos():
    """Loads a set of video IDs that have already been processed."""
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, "r") as f:
        return set(line.strip() for line in f)

def mark_video_as_processed(video_id):
    """Appends the video ID to the processed file."""
    with open(PROCESSED_FILE, "a") as f:
        f.write(f"{video_id}\n")

def extract_video_id(url):
    """Robust extraction for standard, shortened, and mobile YouTube URLs."""
    pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_transcript(video_id):
    """Fetches transcript using the modern object-oriented API calls."""
    try:
        # 1. List available transcripts
        # FIX: Changed the method call from .list() to .list_transcripts()
        transcript_list = YTT_CLIENT.list_transcripts(video_id) 
        
        # 2. Find the best English transcript (Manual preferred over Generated)
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except:
            try:
                # Fallback to auto-generated English
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                logging.warning(f"No English transcript found for {video_id}")
                return None

        # 3. Fetch the actual text data
        lines = transcript.fetch()
        full_text = " ".join([entry['text'] for entry in lines]) 
        
        # 4. Truncate if too long to save cost/errors
        if len(full_text) > MAX_TRANSCRIPT_CHARS:
            logging.info(f"Transcript too long ({len(full_text)} chars). Truncating to {MAX_TRANSCRIPT_CHARS}.")
            return full_text[:MAX_TRANSCRIPT_CHARS] + "..."
            
        return full_text

    except (TranscriptsDisabled, NoTranscriptFound):
        logging.error(f"Transcripts are disabled or not found for video {video_id}")
        return None
    except Exception as e:
        logging.error(f"Error fetching transcript for {video_id}: {e}")
        return None

def generate_tweet_content(transcript_text, video_url):
    """Generates the tweet text using OpenRouter/OpenAI SDK."""
    
    prompt = (
        f"You are a social media manager. Read the following YouTube transcript portion.\n"
        f"Task: Write a single, engaging tweet (MAXIMUM 160 characters) summarizing the core value.\n"
        f"Requirements:\n"
        f"1. Include **one specific, surprising technical fact** or insight from the text.\n"
        f"2. Do NOT use hashtags.\n"
        f"3. Do NOT include the URL in your generated text (I will add it later).\n"
        f"4. The tone should be professional but intriguing. Sound like Andrej Karpathy. Make it sound simple so everyone will understand, don't write more than two well formed sentences.\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        f"TWEET_OUTPUT_START:"
    )

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes viral tweets."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100, 
            temperature=0.7,
        )
        
        tweet_body = response.choices[0].message.content.strip()
        
        # Clean up output
        tweet_body = tweet_body.replace("TWEET_OUTPUT_START:", "").strip()
        if tweet_body.startswith('"') and tweet_body.endswith('"'):
            tweet_body = tweet_body[1:-1]
            
        if not tweet_body:
            logging.warning("LLM returned an empty string for the tweet body.")
            tweet_body = "A must-watch deep dive into the latest tech topic!"

        # Construct final tweet with URL. Twitter shortens the URL to 23 chars.
        final_tweet = f"{tweet_body} {video_url}"
        
        # Safety check: Total tweet length must be <= 280 characters.
        if len(final_tweet) > 280:
            # Max characters for tweet body = 280 - (URL length + 1 space) 
            # Assuming worst case of 280-24 = 256 for the body
            max_body_length = 256 
            
            if len(tweet_body) > max_body_length:
                logging.warning(f"Tweet body generated too long ({len(tweet_body)} chars). Truncating.")
                # Truncate and add ellipsis
                tweet_body = tweet_body[:max_body_length - 3] + "..."
                final_tweet = f"{tweet_body} {video_url}"

        return final_tweet

    except Exception as e:
        logging.error(f"LLM Generation failed: {e}")
        return None

def save_tweet_to_yaml(tweet_text):
    """Appends the new tweet to the YAML file safely."""
    data = {"tweets": []}
    
    if os.path.exists(TWEETS_FILE):
        with open(TWEETS_FILE, "r", encoding="utf-8") as f:
            try:
                existing = yaml.safe_load(f)
                if existing and "tweets" in existing:
                    data = existing
            except yaml.YAMLError:
                logging.error("Could not load existing YAML file. Starting fresh.")

    data["tweets"].append({
        "text": tweet_text,
        "date": datetime.now().isoformat()
    })

    with open(TWEETS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, indent=4)

def post_to_twitter(tweet_text):
    """Posts to Twitter with error handling."""
    try:
        # Load client inside function for better resource management if run infrequently
        client_v2 = tweepy.Client(
            consumer_key=os.environ["CONSUMER_KEY"],
            consumer_secret=os.environ["CONSUMER_SECRET"],
            access_token=os.environ["ACCESS_TOKEN"],
            access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
        )
        
        resp = client_v2.create_tweet(text=tweet_text)
        logging.info(f"Posted single tweet. ID: {resp.data['id']}")
            
        return True
    except Exception as e:
        logging.error(f"Twitter API Error: {e}")
        return False

# --- Main Execution ---

def main():
    if not os.path.exists("videos.txt"):
        logging.error("videos.txt not found. Please create it.")
        return

    processed_videos = load_processed_videos()
    
    with open("videos.txt", "r") as f:
        videos = [line.strip() for line in f if line.strip()]

    for url in videos:
        video_id = extract_video_id(url)
        
        if not video_id:
            logging.warning(f"Invalid URL skipped: {url}")
            continue

        if video_id in processed_videos:
            logging.info(f"Skipping already processed video: {video_id}")
            continue

        logging.info(f"Processing: {url}")

        # 1. Get Transcript
        transcript = get_transcript(video_id)
        if not transcript:
            continue

        # 2. Generate Tweet
        tweet_content = generate_tweet_content(transcript, url)
        if not tweet_content:
            continue

        # 3. Save to YAML (Backup)
        save_tweet_to_yaml(tweet_content)

        # 4. Post to Twitter (Only uncomment this line when ready to post)
        # success = post_to_twitter(tweet_content) 
        # For debugging, we assume success to mark the video as processed unless post_to_twitter is enabled.
        
        success = True # Assume success for logging/testing purposes if post_to_twitter is commented out.

        # 5. Mark as processed only if posting succeeded
        if success:
            mark_video_as_processed(video_id)
            logging.info(f"Successfully processed {video_id}")
            # Add a small delay to respect API limits if processing multiple videos
            time.sleep(5) 

if __name__ == "__main__":
    main()