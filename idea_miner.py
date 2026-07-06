import requests
import os
import re
import time

# --- CONFIGURATION ---
# We use a different webhook for this bot so it posts to a different channel
DISCORD_WEBHOOK_URL = os.getenv("IDEA_MINER_WEBHOOK", "PASTE_YOUR_IDEA_MINER_WEBHOOK_HERE")

# Subreddits where founders and business owners complain about their problems
SUBREDDITS = ['smallbusiness', 'Entrepreneur', 'SaaS', 'startups']

# Regex patterns to find "Pain Points" (Complaints & Requests)
# We use re.IGNORECASE so it catches "Is there a tool", "IS THERE A TOOL", etc.
PAIN_PATTERNS = [
    re.compile(r"is there (a|any) (tool|software|app|service|way)", re.IGNORECASE),
    re.compile(r"looking for (a|an) (tool|software|app|service)", re.IGNORECASE),
    re.compile(r"alternative to", re.IGNORECASE),
    re.compile(r"how do you (handle|manage|track|automate)", re.IGNORECASE),
    re.compile(r"i hate (doing|having to)", re.IGNORECASE),
    re.compile(r"spend (hours|so much time)", re.IGNORECASE),
    re.compile(r"manual(ly)? (doing|process|work)", re.IGNORECASE)
]

def scan_reddit():
    print("🕵️‍♂️ Mining Reddit for startup ideas and pain points...")
    found_ideas = []
    
    # A standard User-Agent is required so Reddit doesn't block GitHub Actions
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) IdeaMiner Bot v1.0'}
    
    for sub in SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            # If we hit a rate limit, wait a bit and try once more
            if response.status_code == 429:
                print(f"⚠️ Rate limited on r/{sub}. Waiting 5 seconds...")
                time.sleep(5)
                response = requests.get(url, headers=headers, timeout=10)
                
            response.raise_for_status()
            posts = response.json()['data']['children']
            
            for post in posts:
                data = post['data']
                title = data.get('title', '')
                selftext = data.get('selftext', '')
                
                # We only want text posts where people are actually writing out their problems
                if not selftext or len(selftext) < 20:
                    continue 
                
                # Combine title and text to check for our pain-point keywords
                full_text = f"{title} {selftext}"
                
                if any(pattern.search(full_text) for pattern in PAIN_PATTERNS):
                    # Truncate the text so it doesn't break Discord's embed limits
                    snippet = selftext[:250].replace('\n', ' ').strip()
                    if len(selftext) > 250:
                        snippet += "..."
                        
                    found_ideas.append({
                        'title': title,
                        'url': f"https://reddit.com{data.get('permalink')}",
                        'subreddit': sub,
                        'snippet': snippet,
                        'ups': data.get('ups', 0)
                    })
                    
            # Be polite to Reddit's servers, wait 2 seconds before checking the next sub
            time.sleep(2) 
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error scanning r/{sub}: {e}")
            continue
            
    # Sort by upvotes so the most agreed-upon pain points show up first
    found_ideas.sort(key=lambda x: x['ups'], reverse=True)
    return found_ideas

def send_to_discord(ideas):
    if not ideas:
        print("No new pain points found today.")
        return
        
    description = "*Raw, unfiltered business problems from Reddit. Build a solution for these!*\n\n"
    
    for idea in ideas[:5]: # Send top 5 ideas
        description += f"🚨 **[{idea['title']}]({idea['url']})**\n"
        description += f"📍 *r/{idea['subreddit']}* | ⬆️ {idea['ups']} upvotes\n"
        description += f"> {idea['snippet']}\n\n"
        
    description += "💡 *See a problem you can solve? DM the author or build it!*"
    
    payload = {
        "username": "The Idea Miner",
        "embeds": [{
            "title": "💡 DAILY STARTUP IDEAS & PAIN POINTS 💡",
            "description": description,
            "color": 15105570 # A nice orange/gold color
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Ideas sent to Discord!")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send to Discord: {e}")

if __name__ == "__main__":
    ideas = scan_reddit()
    send_to_discord(ideas)