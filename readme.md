# Auto Tweet YouTube Summaries

Automate tweeting concise summaries of YouTube videos using Python, OpenAI GPT, and Twitter API, triggered on GitHub Actions for seamless updates.

***

## Features

- Extract YouTube video transcripts automatically
- Generate engaging tweet summaries with AI (OpenAI GPT)
- Append the YouTube video link for context
- Post tweets automatically using Twitter API (Tweepy)
- Run the entire workflow on GitHub Actions triggered on video list update or schedule

***

## Setup Guide

### 1. Prerequisites

- Python 3.10+
- GitHub account
- Twitter Developer account for API keys
- OpenAI API key


### 2. Twitter API Keys

- Sign up for a Twitter Developer account at [developer.twitter.com](https://developer.twitter.com)
- Create a new project/app, generate:
    - Consumer Key (API Key)
    - Consumer Secret (API Secret Key)
    - Access Token
    - Access Token Secret
- Keep these keys safe; you will add them as GitHub secrets.


### 3. OpenAI API Key

- Sign up at [OpenAI](https://platform.openai.com)
- Generate your API key
- Keep it for the secrets setup.


### 4. Project Files

- `youtube_summarizer.py` — Main Python script that:
    - Loads YouTube URLs from `videos.txt`
    - Extracts transcripts
    - Generates tweet summary with OpenAI GPT
    - Saves summary in `tweets.yaml`
    - Posts tweet thread on Twitter
- `videos.txt` — List your YouTube video URLs here (one per line).
- `.github/workflows/auto_tweet.yml` — GitHub Actions workflow to automate script execution.


### 5. Local Setup \& Testing

Clone your GitHub repo (or create one), add the above files, then:

```bash
pip install youtube-transcript-api openai tweepy pyyaml
python youtube_summarizer.py
```

Confirm that the tweets are generated and optionally posted.

### 6. GitHub Setup

- Push your files to GitHub.
- In your repository, go to **Settings > Secrets and variables > Actions**.
- Add secrets:
    - `OPENAI_API_KEY` (your OpenAI key)
    - `CONSUMER_KEY` (Twitter API key)
    - `CONSUMER_SECRET` (Twitter API secret)
    - `ACCESS_TOKEN` (Twitter access token)
    - `ACCESS_TOKEN_SECRET` (Twitter access secret)


### 7. GitHub Actions Workflow

The workflow:

- Triggers on pushes to `videos.txt` or on a schedule
- Sets up Python environment
- Installs dependencies
- Runs `youtube_summarizer.py` to generate and post tweets automatically

Workflow file content (`.github/workflows/auto_tweet.yml`):

```yaml
name: Auto Tweet YouTube Summary

on:
  schedule:
    - cron: '0 * * * *'  # runs hourly, adjust as needed
  push:
    paths:
      - 'videos.txt'

jobs:
  tweet_job:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: 3.10

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install youtube-transcript-api openai tweepy pyyaml

      - name: Run YouTube Summarizer and Tweet
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          CONSUMER_KEY: ${{ secrets.CONSUMER_KEY }}
          CONSUMER_SECRET: ${{ secrets.CONSUMER_SECRET }}
          ACCESS_TOKEN: ${{ secrets.ACCESS_TOKEN }}
          ACCESS_TOKEN_SECRET: ${{ secrets.ACCESS_TOKEN_SECRET }}
        run: python youtube_summarizer.py
```


### 8. Usage

- Add new YouTube URLs to `videos.txt`
- Push changes to trigger tweets automatically or wait for scheduled workflow
- Tweets will contain AI-generated summaries and YouTube links

***

## Additional Tips

- Customize the OpenAI prompt in the script for different summary styles
- Cache processed videos to avoid duplicate tweets (add persistence)
- Extend tweet threads with multiple summary parts if needed

***

## References

- [Twitter Developer Portal](https://developer.twitter.com)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [youtube-transcript-api GitHub](https://github.com/jdepoix/youtube-transcript-api)
- [Tweepy Documentation](https://docs.tweepy.org/en/stable/)
- [GitHub Actions Documentation](https://docs.github.com/actions)

