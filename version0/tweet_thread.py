import os
import yaml
import tweepy

def load_tweets_from_yaml(path="tweets.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("tweets", [])

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
            response = client.create_tweet(text=tweet, in_reply_to_tweet_id=last_tweet_id)
        else:
            response = client.create_tweet(text=tweet)
        last_tweet_id = response.data["id"]
        print(f"Tweet posted with ID: {last_tweet_id}")

if __name__ == "__main__":
    tweets = load_tweets_from_yaml()
    if tweets:
        post_thread(tweets)
    else:
        print("No tweets found in tweets.yaml")
