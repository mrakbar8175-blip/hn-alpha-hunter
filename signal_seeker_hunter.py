import requests
import os
import json
import re

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("SIGNAL_HUNTER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")
STATE_FILE = "sent_signal_seeks.json"

# We search Hacker News for crypto pain points (unblockable and free)
SEARCH_QUERIES = [
    "crypto lost", "got rekt", "liquidated", "signal group", 
    "crypto scam", "trading bot", "lost my bitcoin", "futures"
]

def load_sent_seeks():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_sent_seeks(sent_set):
    recent_urls = list(sent_set)[-500:]
    with open(STATE_FILE, 'w') as f:
        json.dump(recent_urls, f)

def scan_for_seekers():
    print("🕵️‍♂️ Hunting for crypto traders in pain (via Hacker News)...")
    found_seeks = []
    
    # Algolia's search_by_date gets the freshest complaints
    base_url = "https://hn.algolia.com/api/v1/search_by_date"
    
    for query in SEARCH_QUERIES:
        params = {
            "query": query,
            "tags": "(story,ask_hn) OR comment", 
            "hitsPerPage": 10
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            hits = response.json().get('hits', [])
            
            for hit in hits:
                item_id = hit.get('objectID')
                
                # Get the correct URL (Article link or HN discussion link)
                if hit.get('url'):
                    item_url = hit['url']
                else:
                    item_url = f"https://news.ycombinator.com/item?id={item_id}"
                    
                # Get the text (comment or title)
                text_content = hit.get('comment_text') or hit.get('story_title') or hit.get('title', '')
                
                # Clean up the HTML tags that Algolia returns
                text_content = re.sub(r'<[^>]+>', '', text_content).replace('&amp;', '&').replace('&quot;', '"').replace('&#x27;', "'").strip()
                
                snippet = text_content[:200] + ("..." if len(text_content) > 200 else "")
                
                found_seeks.append({
                    'title': hit.get('story_title') or hit.get('title') or "Crypto Discussion",
                    'url': item_url,
                    'snippet': snippet,
                })
                
        except Exception as e:
            print(f"❌ Error searching for '{query}': {e}")
            continue
            
    # Remove duplicates based on URL
    unique_seeks = {}
    for seek in found_seeks:
        if seek['url'] not in unique_seeks:
            unique_seeks[seek['url']] = seek
            
    return list(unique_seeks.values())

def send_to_discord(seeks):
    if not seeks:
        print("No new signal seekers found.")
        return
    
    description = "*People talking about crypto struggles. Perfect leads for your signals!*\n\n"
    
    for seek in seeks[:5]:
        description += f"🚨 **[{seek['title']}]({seek['url']})**\n"
        description += f"> {seek['snippet']}\n\n"
    
    description += "💡 *Action: Reply with value, or if it's an article, comment on the forum!*"
    
    payload = {
        "username": "Signal Seeker Hunter",
        "embeds": [{
            "title": "🔥 CRYPTO TRADERS IN PAIN - HOT LEADS 🔥",
            "description": description,
            "color": 15105570
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Signal seekers sent to Discord!")
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")

if __name__ == "__main__":
    already_sent = load_sent_seeks()
    all_seeks = scan_for_seekers()
    new_seeks = [s for s in all_seeks if s['url'] not in already_sent]
    
    if new_seeks:
        print(f"🎉 Found {len(new_seeks)} NEW signal seekers!")
        send_to_discord(new_seeks)
        for s in new_seeks:
            already_sent.add(s['url'])
            
    # 👇 ALWAYS save the state file so GitHub Actions doesn't crash!
    save_sent_seeks(already_sent)
    print("💾 Saved state.")