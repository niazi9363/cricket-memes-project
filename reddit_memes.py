import os
import sys
import time
import requests
from dotenv import load_dotenv

# Ensure standard output uses UTF-8 encoding (prevents emoji print errors on Windows)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")

if FB_PAGE_ID:
    FB_PAGE_ID = FB_PAGE_ID.strip()
if FB_ACCESS_TOKEN:
    FB_ACCESS_TOKEN = FB_ACCESS_TOKEN.strip()

POSTED_IDS_FILE = "posted_ids.txt"
REDDIT_URL = "https://old.reddit.com/r/CricketShitpost/top/.rss?t=day"

# Browser headers to avoid 403 blocks on residential IPs
REDDIT_HEADERS = {
    "User-Agent": "script:cricket_memes_fb_bot:v1.0.0 (by /u/zohaibking9363)"
}

def load_posted_ids():
    """Loads previously posted Reddit post IDs to avoid duplicates."""
    if not os.path.exists(POSTED_IDS_FILE):
        return set()
    try:
        with open(POSTED_IDS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"[-] Error reading {POSTED_IDS_FILE}: {e}")
        return set()

def save_posted_id(post_id):
    """Saves a successfully posted Reddit post ID to prevent posting it again."""
    try:
        with open(POSTED_IDS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{post_id}\n")
    except Exception as e:
        print(f"[-] Error saving posted ID {post_id}: {e}")

def get_top_memes(posted_ids):
    """Scrapes top daily memes using the RSS feed and filters the top 5 new image posts."""
    print(f"[*] Fetching top memes from RSS feed...")
    try:
        response = requests.get(REDDIT_URL, headers=REDDIT_HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"[-] Failed to fetch Reddit RSS feed. Status code: {response.status_code}")
            if response.status_code in (403, 429):
                print("    > Note: Reddit is blocking automated requests from this network context.")
            return []
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'xml')
        entries = soup.find_all('entry')
        
        memes = []
        for entry in entries:
            # Extract raw ID (e.g. tag:reddit.com,2008:post/t3_1tvoa86 -> t3_1tvoa86 or 1tvoa86)
            raw_id = entry.find('id').text if entry.find('id') else ""
            post_id = raw_id.split('/')[-1] if '/' in raw_id else raw_id
            
            # Clean up the t3_ prefix if it exists
            if post_id.startswith("t3_"):
                post_id = post_id[3:]
                
            if not post_id or post_id in posted_ids:
                continue
                
            # Parse HTML content inside entry
            content_html = entry.find('content').text if entry.find('content') else ""
            if not content_html:
                continue
                
            content_soup = BeautifulSoup(content_html, 'html.parser')
            link_tag = content_soup.find('a', string='[link]')
            url = link_tag.get('href') if link_tag else ""
            
            if not url:
                continue
                
            # Filter for image posts (ending in png, jpg, jpeg, gif)
            is_image = any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif"])
            if not is_image:
                continue
                
            title = entry.find('title').text if entry.find('title') else "Meme"
            
            author_tag = entry.find('author')
            name_tag = author_tag.find('name') if author_tag else None
            author = name_tag.text.replace('/u/', '').strip() if name_tag else "anonymous"
            
            memes.append({
                "id": post_id,
                "title": title,
                "author": author,
                "url": url
            })
            
            if len(memes) >= 5:
                break
                
        return memes
    except Exception as e:
        print(f"[-] Exception occurred while parsing RSS: {e}")
        return []

def post_photo_to_facebook(image_url, caption, dry_run=False):
    """Posts an image via URL directly with a caption to the configured Facebook Page."""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        print("[-] Error: FB_PAGE_ID or FB_ACCESS_TOKEN is missing in the environment.")
        return False
        
    if dry_run:
        print("[*] [Dry-Run] Simulating Facebook photo post...")
        print(f"    Caption:\n{caption}")
        return True
        
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
    payload = {
        "url": image_url,
        "caption": caption,
        "access_token": FB_ACCESS_TOKEN
    }
    
    try:
        print("[*] Uploading photo via URL to Facebook Page...")
        response = requests.post(url, data=payload, timeout=30)
        res_json = response.json()
        
        if response.status_code == 200 and "id" in res_json:
            print(f"[+] Post successful! Photo ID: {res_json['id']}")
            return True
        else:
            print(f"[-] Facebook API Error: {res_json}")
            return False
    except Exception as e:
        print(f"[-] Exception posting to Facebook: {e}")
        return False

def run_meme_poster(dry_run=False):
    """Orchestrates the meme fetching, posting, and ID saving process."""
    print("\n" + "="*50)
    print(f"[*] Cycle Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    posted_ids = load_posted_ids()
    memes = get_top_memes(posted_ids)
    
    if not memes:
        print("[-] No new memes to process in this cycle.")
        return
        
    print(f"[+] Found {len(memes)} new memes to process.")
    
    for i, meme in enumerate(memes, 1):
        print(f"\n[{i}/{len(memes)}] Processing Meme ID: {meme['id']}")
        
        # Create caption with funny emojis and professional layout
        caption = (
            f"{meme['title']} 😂🏏\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"#CricketMemes #CricketFans #MemeOfTheDay"
        )
        
        # Post directly to Facebook Page using the Reddit image URL
        success = post_photo_to_facebook(meme['url'], caption, dry_run=dry_run)
        
        # If successfully posted, save ID to avoid duplicates
        if success and not dry_run:
            save_posted_id(meme['id'])
        
        # Subtle sleep between posts to prevent rapid api hit issues
        if i < len(memes):
            time.sleep(5)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Reddit Cricket Meme Facebook Bot")
    parser.add_argument("--once", action="store_true", help="Run once and exit immediately.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate scraping and post formatting without publishing.")
    args = parser.parse_args()
    
    if args.dry_run:
        print("[*] Bot running in DRY RUN mode (Console Output Only).")
        
    if args.once:
        print("[*] Running in single-run mode...")
        run_meme_poster(dry_run=args.dry_run)
    else:
        print("[*] Continuous mode started. Bot will check and post every 2 hours.")
        # Execute immediately on startup
        run_meme_poster(dry_run=args.dry_run)
        
        # Continuous loop
        interval = 7200  # 2 hours in seconds
        try:
            while True:
                print(f"\n[*] Sleeping for 2 hours...")
                time.sleep(interval)
                run_meme_poster(dry_run=args.dry_run)
        except KeyboardInterrupt:
            print("\n[*] Bot stopped by user.")

if __name__ == "__main__":
    main()