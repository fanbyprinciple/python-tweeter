import re
import yaml
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI  # assume you have OpenAI Python client installed and configured

def extract_video_id(url):
    """
    Extract the YouTube video ID from a URL.
    Supports standard and shortened URLs.
    """
    pattern = (r"(?:v=|\/)([0-9A-Za-z_-]{11}).*")
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_transcript(video_id):
    """
    Fetch the transcript text (English or auto-generated if available).
    Joins all transcript parts into one string.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en'])
        lines = transcript.fetch()
        text = " ".join([entry['text'] for entry in lines])
        return text
    except Exception as e:
        print(f"Could not retrieve transcript: {e}")
        return ""

def generate_tweet_summary(text, video_title):
    """
    Use OpenAI GPT to generate a tweet-like summary introducing the video to an uninformed audience.
    """
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
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=60,
        temperature=0.7,
    )
    tweet = response.choices[0].message.content.strip()
    return tweet

def save_tweets_to_yaml(tweets, filename="tweets.yaml"):
    """
    Save tweets to a YAML file as a list under "tweets" key.
    """
    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump({"tweets": tweets}, f, allow_unicode=True)

def main(youtube_url):
    video_id = extract_video_id(youtube_url)
    if not video_id:
        print("Invalid YouTube URL")
        return

    transcript_text = get_transcript(video_id)
    if not transcript_text:
        print("No transcript available.")
        return

    # You can optionally fetch the video title via YouTube API or some other method.
    # Here we set a placeholder title to keep the example simple.
    video_title = "YouTube Video"

    tweet_summary = generate_tweet_summary(transcript_text, video_title)

    print("Generated Tweet Summary:")
    print(tweet_summary)

    save_tweets_to_yaml([tweet_summary])
    print(f"Tweet saved to tweets.yaml")

if __name__ == "__main__":
    yt_url = input("Enter YouTube video URL: ")
    main(yt_url)
