import re
import yaml
import os
import logging
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from openai import OpenAI
import tweepy
from dotenv import load_dotenv

# --- Configuration & Setup ---
load_dotenv()

# Logging setup for debugging
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
MAX_TRANSCRIPT_CHARS = 15000  # Approx 3-4k tokens to prevent context overflow
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "openai/gpt-oss-20b:free" # Or "meta-llama/llama-3-8b-instruct:free"

# Initialize OpenAI Client (OpenRouter compatible)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

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
    # Handles: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID
    pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_transcript(video_id):
    """Fetches transcript with fallbacks for generated subs."""
    try:
        # Try fetching manually created transcripts first, fallback to generated
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Prioritize English, fallback to auto-generated English
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                # If no English, take whatever is available (optional)
                return None

        lines = transcript.fetch()
        full_text = " ".join([entry['text'] for entry in lines])
        
        # Truncate if too long to save cost/errors
        if len(full_text) > MAX_TRANSCRIPT_CHARS:
            logging.info(f"Transcript too long ({len(full_text)} chars). Truncating to {MAX_TRANSCRIPT_CHARS}.")
            return full_text[:MAX_TRANSCRIPT_CHARS] + "..."
            
        return full_text

    except (TranscriptsDisabled, NoTranscriptFound):
        logging.error(f"Transcripts disabled or not found for {video_id}")
        return None
    except Exception as e:
        logging.error(f"Error fetching transcript for {video_id}: {e}")
        return None

def generate_tweet_content(transcript_text, video_url):
    """Generates the tweet text using OpenRouter/OpenAI SDK."""
    
    prompt = (
        f"You are a social media manager. Read the following YouTube transcript portion.\n"
        f"Task: Write a single, engaging tweet (MAXIMUM 240 characters) summarizing the core value.\n"
        f"Requirements:\n"
        f"1. Include one specific, surprising technical fact or insight from the text.\n"
        f"2. Do NOT use hashtags.\n"
        f"3. Do NOT include the URL in your generated text (I will add it later).\n"
        f"4. Tone: Professional but intriguing.\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        f"Tweet:"
    )

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes viral tweets."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100, # Keep generation short
            temperature=0.7,
        )
        
        tweet_body = response.choices[0].message.content.strip()
        
        # Clean up if LLM wrapped it in quotes
        if tweet_body.startswith('"') and tweet_body.endswith('"'):
            tweet_body = tweet_body[1:-1]

        # Construct final tweet with URL
        final_tweet = f"{tweet_body}\n\nWatch here: {video_url}"
        return final_tweet

    except Exception as e:
        logging.error(f"LLM Generation failed: {e}")
        return None

def save_tweet_to_yaml(tweet_text):
    """Appends the new tweet to the YAML file safely."""
    data = {"tweets": []}
    
    if os.path.exists(TWEETS_FILE):
        with open(TWEETS_FILE, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f)
            if existing and "tweets" in existing:
                data = existing
    
    data["tweets"].append({
        "text": tweet_text,
        "date": datetime.now().isoformat()
    })

    with open(TWEETS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)

def post_to_twitter(tweet_text):
    """Posts to Twitter with error handling."""
    try:
        client_v2 = tweepy.Client(
            consumer_key=os.environ["CONSUMER_KEY"],
            consumer_secret=os.environ["CONSUMER_SECRET"],
            access_token=os.environ["ACCESS_TOKEN"],
            access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
        )
        
        # Split logic if tweet is somehow still too long (Safety net)
        if len(tweet_text) > 280:
            logging.warning("Tweet exceeded 280 chars. Posting as thread.")
            # Basic split (naive) - ideally you'd split by sentence
            part1 = tweet_text[:270] + "..."
            part2 = "..." + tweet_text[270:]
            
            resp1 = client_v2.create_tweet(text=part1)
            client_v2.create_tweet(text=part2, in_reply_to_tweet_id=resp1.data['id'])
            logging.info(f"Posted thread. ID: {resp1.data['id']}")
        else:
            resp = client_v2.create_tweet(text=tweet_text)
            logging.info(f"Posted single tweet. ID: {resp.data['id']}")
            
        return True
    except Exception as e:
        logging.error(f"Twitter API Error: {e}")
        return False

def main():
    if not os.path.exists("videos.txt"):
        logging.error("videos.txt not found. Please create it.")
        return

    # Load processed videos history
    processed_videos = load_processed_videos()
    
    with open("videos.txt", "r") as f:
        # Filter out empty lines
        videos = [line.strip() for line in f if line.strip()]

    for url in videos:
        video_id = extract_video_id(url)
        
        if not video_id:
            logging.warning(f"Invalid URL skipped: {url}")
            continue

        # Skip if already done
        if video_id in processed_videos:
            logging.info(f"Skipping already processed video: {video_id}")
            continue

        logging.info(f"Processing: {url}")

        # 1. Get Transcript
        transcript = get_transcript(video_id)
        if not transcript:
            continue # Skip to next video if transcript fails

        # 2. Generate Tweet
        tweet_content = generate_tweet_content(transcript, url)
        if not tweet_content:
            continue

        # 3. Save to YAML (Backup)
        save_tweet_to_yaml(tweet_content)

        # 4. Post to Twitter
        success = post_to_twitter(tweet_content)
        
        # 5. Mark as processed only if posting (or saving) worked
        if success:
            mark_video_as_processed(video_id)
            logging.info(f"Successfully processed {video_id}")

if __name__ == "__main__":
    main()