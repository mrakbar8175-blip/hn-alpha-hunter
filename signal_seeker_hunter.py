import requests
import os
import json
import re

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("SIGNAL_HUNTER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")
STATE_FILE = "sent_signal_seeks.json"

# Subreddits where crypto traders hang out and complain
SUBREDDITS = ['CryptoCurrency', 'Bitcoin', 'ethtrader', 'CryptoMarkets', 'altcoin', 'CryptoTrading']

# Phrases that indicate someone is struggling and needs signals
PAIN_PHRASES = [
    "lost money", "got rekt", "liquidated", "down bad", 
    "looking for signals", "need signals", "signal group", 
    "recommend signal", "which signal", "signal service",
    "bad signals", "fake signals", "scammed", "rug pull",
    "need help trading", "how to trade", "trading help",
    "lost all", "portfolio down", "bleeding money",
    "stop loss", "take profit", "when to sell", "when to buy",
    "missed the pump", "bought the top", "sold the bottom"
]

def load_sent_seeks():
    """Loads the memory file to see what we already posted."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_sent_seeks(sent_set):
    """Saves the memory file. Keeps only the last 300."""
    recent_urls = list(sent_set)[-300:]
    with open(STATE_FILE, 'w') as f:
        json.dump(recent_urls, f)

def scan_reddit_for_seekers():
    print(" Hunting for crypto traders in pain...")
    found_seeks = []
    
    headers = {'User-Agent': 'SignalSeekerHunter/1.0'}
    
    for sub in SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=50"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 429:
                print(f"️ Rate limited on r/{sub}. Waiting...")
                import time
                time.sleep(5)
                response = requests.get(url, headers=headers, timeout=10)
                
            response.raise_for_status()
            posts = response.json()['data']['children']
            
            for post in posts:
                data = post['data']
                title = data.get('title', '').lower()
                selftext = data.get('selftext', '').lower()
                
                # Skip if no text content
                if not selftext and len(title) < 20:
                    continue
                
                full_text = f"{title} {selftext}"
                
                # Check if post contains pain phrases
                if any(phrase in full_text for phrase in PAIN_PHRASES):
                    # Calculate how much they're struggling (word match count)
                    pain_score = sum(1 for phrase in PAIN_PHRASES if phrase in full_text)
                    
                    # Only post if they have at least 2 pain indicators
                    if pain_score >= 2:
                        snippet = selftext[:200].replace('\n', ' ').strip() if selftext else title
                        if len(selftext) > 200:
                            snippet += "..."
                        
                        found_seeks.append({
                            'title': data.get('title', ''),
                            'url': f"https://reddit.com{data.get('permalink')}",
                            'subreddit': sub,
                            'snippet': snippet,
                            'score': data.get('score', 0),
                            'pain_score': pain_score,
                            'created': data.get('created_utc', 0)
                        })
            
            import time
            time.sleep(2)  # Be polite to Reddit
            
        except Exception as e:
            print(f"❌ Error scanning r/{sub}: {e}")
            continue
    
    # Sort by pain score (most desperate first) and recency
    found_seeks.sort(key=lambda x: (x['pain_score'], -x['created']), reverse=True)
    return found_seeks[:10]  # Return top 10 most promising leads

def send_to_discord(seeks):
    if not seeks:
        print("No new signal seekers found.")
        return
    
    description = "*People actively looking for help with crypto trading. Perfect leads for your signals!*\n\n"
    
    for seek in seeks[:5]:  # Send top 5
        description += f" **[{seek['title']}]({seek['url']})**\n"
        description += f"📍 *r/{seek['subreddit']}* | Pain Level: {'🔴' * seek['pain_score']} ({seek['pain_score']}/10)\n"
        description += f"> {seek['snippet']}\n\n"
    
    description += "💡 *Action: Reply with value first, then mention your Signal server!*"
    
    payload = {
        "username": "Signal Seeker Hunter",
        "embeds": [{
            "title": "🔥 CRYPTO TRADERS IN PAIN - HOT LEADS 🔥",
            "description": description,
            "color": 15105570  # Orange
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Signal seekers sent to Discord!")
    except Exception as e:
        print(f" Failed to send to Discord: {e}")

if __name__ == "__main__":
    # 1. Load history
    already_sent = load_sent_seeks()
    
    # 2. Find new seekers
    all_seeks = scan_reddit_for_seekers()
    
    # 3. Filter duplicates
    new_seeks = [s for s in all_seeks if s['url'] not in already_sent]
    
    if new_seeks:
        print(f"🎉 Found {len(new_seeks)} NEW signal seekers!")
        send_to_discord(new_seeks)
        
        # 4. Save to memory
        for s in new_seeks:
            already_sent.add(s['url'])
        save_sent_seeks(already_sent)
        print("💾 Saved state to prevent duplicates.")
    else:
        print("No new seekers found (already tracking recent posts).")