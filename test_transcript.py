from youtube_transcript_api import YouTubeTranscriptApi

video_id = "lznmsF4-afA" # The video ID that failed for you

try:
    # This uses the modern, preferred method
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    print("SUCCESS: list_transcripts exists and was found!")
except AttributeError as e:
    print(e)
    print(f"FAILURE: {e}. The installation is definitely broken.")
except Exception as e:
    print(f"SUCCESS: The module is loading, but transcript fetching failed: {e}")