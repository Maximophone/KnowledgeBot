from integrations.twitter_api import TwitterAPI

def main():
    # Initialize the Twitter API
    twitter = TwitterAPI()
    
    # Example thread URL
    thread_url = "https://x.com/Yoshua_Bengio/status/1884593469265502482"
    
    # Convert thread to markdown
    markdown = twitter.thread_to_markdown(thread_url)
    
    if markdown:
        print("Successfully converted thread to markdown:")
        print("\n" + markdown)
    else:
        print("Failed to convert thread to markdown")

if __name__ == "__main__":
    main() 