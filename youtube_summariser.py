import re
import yaml
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
import tweepy
import os


def extract_video_id(url):
    pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en'])
        lines = transcript.fetch()
        text = " ".join([entry['text'] for entry in lines])
        return text
    except Exception as e:
        print(f"Could not retrieve transcript: {e}")
        return ""

def generate_tweet_summary(text, video_title="YouTube Video", video_url=""):
    client = OpenAI()

    prompt = (
        f"Summarize this YouTube video transcript into one concise tweet "
        f"that introduces the video to an audience unaware of its context.\n\n"
        f"Video Title: {video_title}\n"
        f"Transcript: {text}\n\n"
        f"Tweet:"
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0.7,
    )
    tweet = response.choices[0].message.content.strip()
    # Append video URL for more info
    return f"{tweet}\nWatch here: {video_url}"

def process_video(youtube_url, post_tweet=True):
    video_id = extract_video_id(youtube_url)
    if not video_id:
        print("Invalid YouTube URL")
        return

    transcript = get_transcript(video_id)
    if not transcript:
        print("No transcript available.")
        return

    tweet_summary = generate_tweet_summary(transcript, video_url=youtube_url)

    print(f"Generated Tweet Summary:\n{tweet_summary}")

    save_tweets_to_yaml([tweet_summary])

    if post_tweet:
        post_thread([tweet_summary])


def save_tweets_to_yaml(tweets, filename="tweets.yaml"):
    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump({"tweets": tweets}, f, allow_unicode=True)

def load_twitter_client():
    return tweepy.Client(
        consumer_key=os.environ["CONSUMER_KEY"],
        consumer_secret=os.environ["CONSUMER_SECRET"],
        access_token=os.environ["ACCESS_TOKEN"],
        access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
    )

def post_thread(tweets, reply_thread=True):
    client = load_twitter_client()
    last_tweet_id = None

    for tweet in tweets:
        if reply_thread and last_tweet_id:
            resp = client.create_tweet(text=tweet, in_reply_to_tweet_id=last_tweet_id)
        else:
            resp = client.create_tweet(text=tweet)
        last_tweet_id = resp.data["id"]
        print(f"Posted tweet ID: {last_tweet_id}")


def main():
    # Example loader from videos.txt with one YouTube URL per line
    # Manage this file to add new videos
    if not os.path.exists("videos.txt"):
        print("Create a videos.txt file with YouTube URLs, one per line.")
        return

    with open("videos.txt", "r") as f:
        videos = [line.strip() for line in f if line.strip()]

    for url in videos:
        process_video(url)

if __name__ == "__main__":
    main()
