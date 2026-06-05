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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/xml, application/xhtml+xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
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

def download_image(url, post_id):
    """Downloads the image locally and returns the temporary file path."""
    # Determine the file extension
    ext = ".jpg"
    for possible_ext in [".png", ".gif", ".jpeg", ".jpg"]:
        if url.lower().endswith(possible_ext):
            ext = possible_ext
            break
            
    temp_filename = f"temp_{post_id}{ext}"
    try:
        print(f"[*] Downloading image: {url}")
        response = requests.get(url, headers=REDDIT_HEADERS, timeout=20)
        if response.status_code == 200:
            with open(temp_filename, 'wb') as f:
                f.write(response.content)
            return temp_filename
        else:
            print(f"[-] Failed to download image. Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"[-] Exception downloading image from {url}: {e}")
        return None

def post_photo_to_facebook(image_path, caption, dry_run=False):
    """Posts a local image with a caption to the configured Facebook Page."""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        print("[-] Error: FB_PAGE_ID or FB_ACCESS_TOKEN is missing in the environment.")
        return False
        
    if dry_run:
        print("[*] [Dry-Run] Simulating Facebook photo post...")
        print(f"    Caption:\n{caption}")
        return True
        
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
    payload = {
        "caption": caption,
        "access_token": FB_ACCESS_TOKEN
    }
    
    try:
        with open(image_path, 'rb') as img_file:
            files = {
                "source": img_file
            }
            print("[*] Uploading photo to Facebook Page...")
            response = requests.post(url, data=payload, files=files, timeout=30)
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

def clean_up_file(file_path):
    """Safely deletes the temporary downloaded image file."""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[+] Cleaned up temporary file: {file_path}")
        except Exception as e:
            print(f"[-] Error deleting temporary file {file_path}: {e}")

def run_meme_poster(dry_run=False):
    """Orchestrates the meme fetching, downloading, posting, and cleanup process."""
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
        
        # Download image
        image_path = download_image(meme['url'], meme['id'])
        if not image_path:
            print(f"[-] Skipping meme {meme['id']} due to download failure.")
            continue
            
        # Create caption with funny emojis and professional layout (no credits or bot signatures)
        caption = (
            f"{meme['title']} 😂🏏\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"#CricketMemes #CricketFans #MemeOfTheDay"
        )
        
        # Post to Facebook Page
        success = post_photo_to_facebook(image_path, caption, dry_run=dry_run)
        
        # If successfully posted, save ID to avoid duplicates
        if success and not dry_run:
            save_posted_id(meme['id'])
            
        # Clean up the file
        clean_up_file(image_path)
        
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
