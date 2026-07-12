import requests
import os
import json
import re

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("SIGNAL_HUNTER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")
STATE_FILE = "sent_signal_seeks.json"

# The best crypto subreddits where people complain
SUBREDDITS = ['CryptoCurrency', 'Bitcoin', 'CryptoMarkets', 'altcoin']

# The Free Proxy to bypass GitHub Actions IP block
PROXY_URL = "https://api.allorigins.win/raw?url="

# Pain keywords
PAIN_KEYWORDS = [
    "lost money", "lost all", "got rekt", "rekt", "liquidated",
    "need help", "help me", "struggling", "losing money", "down bad",
    "scammed", "rug pull", "fake signals", "bad signals", "lost everything",
    "broke", "don't know what to do", "confused", "selling everything",
    "giving up", "quit trading", "worst trade", "huge loss"
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

def scan_reddit():
    print("🕵️‍♂️ Hunting for traders in pain on Reddit...")
    found_leads = []
    
    for sub in SUBREDDITS:
        # We wrap the Reddit URL in the free proxy to bypass the 403 block
        target_url = f"https://www.reddit.com/r/{sub}/new.json?limit=50"
        proxy_request_url = f"{PROXY_URL}{target_url}"
        
        try:
            # No special headers needed, the proxy handles it
            response = requests.get(proxy_request_url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            posts = data.get('data', {}).get('children', [])
            
            for post in posts:
                post_data = post.get('data', {})
                
                # Skip if it's not a text post or has no text
                if not post_data.get('selftext'):
                    continue
                    
                title = post_data.get('title', '').lower()
                text = post_data.get('selftext', '').lower()
                full_text = f"{title} {text}"
                
                # Check for pain keywords
                matches = [kw for kw in PAIN_KEYWORDS if kw in full_text]
                
                # Only flag if they have at least 2 pain indicators
                if len(matches) >= 2:
                    author = post_data.get('author', 'Unknown')
                    permalink = post_data.get('permalink', '')
                    post_id = post_data.get('id', '')
                    
                    snippet = post_data.get('selftext', '')[:150]
                    if len(post_data.get('selftext', '')) > 150:
                        snippet += "..."
                        
                    found_leads.append({
                        'author': author,
                        'title': post_data.get('title', ''),
                        'snippet': snippet,
                        'url': f"https://reddit.com{permalink}",
                        'post_id': post_id,
                        'pain_score': len(matches),
                        'matches': ", ".join(matches[:3])
                    })
                    
        except Exception as e:
            print(f"️ Error scanning r/{sub}: {e}")
            continue
            
    # Sort by pain score (most desperate first)
    found_leads.sort(key=lambda x: x['pain_score'], reverse=True)
    return found_leads

def send_to_discord(leads):
    if not leads:
        print("No new people in pain found.")
        return
        
    description = "*REAL PEOPLE on Reddit struggling with crypto. Reply with value, then mention your server.*\n\n"
    
    for lead in leads[:8]:
        description += f"👤 **u/{lead['author']}** | Pain: {'🔴' * lead['pain_score']}\n"
        description += f"📝 **{lead['title']}**\n"
        description += f"💬 > {lead['snippet']}\n"
        description += f"🔗 [Reply Here]({lead['url']}) | Keywords: `{lead['matches']}`\n\n"
        
    description += "💡 *Strategy: Reply with empathy + free tip, then softly mention your signal server.*"
    
    payload = {
        "username": "Signal Seeker Hunter",
        "embeds": [{
            "title": "🔥 REAL TRADERS IN PAIN - REDDIT LEADS 🔥",
            "description": description,
            "color": 15105570
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Leads sent to Discord!")
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")

if __name__ == "__main__":
    already_sent = load_sent_seeks()
    all_leads = scan_reddit()
    
    # Filter out duplicates using the post ID
    new_leads = [l for l in all_leads if l['post_id'] not in already_sent]
    
    if new_leads:
        print(f"🎉 Found {len(new_leads)} NEW people in pain!")
        send_to_discord(new_leads)
        for l in new_leads:
            already_sent.add(l['post_id'])
    
    # ALWAYS save state
    save_sent_seeks(already_sent)
    print("💾 State saved.")