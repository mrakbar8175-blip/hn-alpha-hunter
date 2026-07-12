import requests
import os
import json
import re

DISCORD_WEBHOOK_URL = os.getenv("SIGNAL_HUNTER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")
STATE_FILE = "sent_signal_seeks.json"

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

def scan_hackernews():
    """Engine 1: 100% unblockable, high-quality crypto traders."""
    print(" Engine 1: Scanning Hacker News for crypto pain...")
    found_leads = []
    
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": "crypto OR bitcoin OR ethereum OR trading",
        "tags": "comment", # We want comments where people complain
        "hitsPerPage": 50,
        "numericFilters": "points>0"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        hits = response.json().get('hits', [])
        
        for hit in hits:
            text = hit.get('comment_text', '').lower()
            # Remove HTML tags from HN comments
            text = re.sub('<[^<]+?>', '', text)
            
            matches = [kw for kw in PAIN_KEYWORDS if kw in text]
            
            if len(matches) >= 1:
                author = hit.get('author', 'Unknown')
                story_title = hit.get('story_title', 'Unknown')
                object_id = hit.get('objectID')
                
                snippet = text[:150]
                if len(text) > 150:
                    snippet += "..."
                    
                found_leads.append({
                    'author': author,
                    'platform': 'Hacker News',
                    'title': f"Re: {story_title}",
                    'snippet': snippet,
                    'url': f"https://news.ycombinator.com/item?id={object_id}",
                    'id': f"hn_{object_id}",
                    'pain_score': len(matches),
                    'matches': ", ".join(matches[:3])
                })
    except Exception as e:
        print(f"⚠️ Engine 1 failed: {e}")
        
    return found_leads

def scan_reddit_proxy():
    """Engine 2: Reddit via reliable CORS proxy."""
    print("🔍 Engine 2: Scanning Reddit via proxy...")
    found_leads = []
    
    subreddits = ['CryptoCurrency', 'Bitcoin', 'CryptoMarkets']
    # Highly reliable proxy
    proxy = "https://corsproxy.io/?"
    
    for sub in subreddits:
        target_url = f"https://www.reddit.com/r/{sub}/new.json?limit=30"
        
        try:
            response = requests.get(f"{proxy}{target_url}", timeout=15)
            response.raise_for_status()
            data = response.json()
            posts = data.get('data', {}).get('children', [])
            
            for post in posts:
                post_data = post.get('data', {})
                if not post_data.get('selftext'):
                    continue
                    
                title = post_data.get('title', '').lower()
                text = post_data.get('selftext', '').lower()
                full_text = f"{title} {text}"
                
                matches = [kw for kw in PAIN_KEYWORDS if kw in full_text]
                
                if len(matches) >= 2:
                    author = post_data.get('author', 'Unknown')
                    post_id = post_data.get('id', '')
                    permalink = post_data.get('permalink', '')
                    
                    snippet = post_data.get('selftext', '')[:150]
                    if len(post_data.get('selftext', '')) > 150:
                        snippet += "..."
                        
                    found_leads.append({
                        'author': author,
                        'platform': 'Reddit',
                        'title': post_data.get('title', ''),
                        'snippet': snippet,
                        'url': f"https://reddit.com{permalink}",
                        'id': f"reddit_{post_id}",
                        'pain_score': len(matches),
                        'matches': ", ".join(matches[:3])
                    })
        except Exception as e:
            print(f"⚠️ Engine 2 failed for r/{sub}: {e}")
            continue
            
    return found_leads

def send_to_discord(leads):
    if not leads:
        print("❌ No new people in pain found.")
        return
        
    description = "*REAL PEOPLE struggling with crypto. Reply with value, then mention your server.*\n\n"
    
    for lead in leads[:8]:
        platform_emoji = "🟠" if lead['platform'] == 'Hacker News' else ""
        description += f"{platform_emoji} **{lead['author']}** ({lead['platform']}) | Pain: {'🔴' * lead['pain_score']}\n"
        description += f"📝 **{lead['title']}**\n"
        description += f"💬 > {lead['snippet']}\n"
        description += f"🔗 [Reply Here]({lead['url']})\n\n"
        
    description += "💡 *Strategy: Reply with empathy + free tip, then softly mention your signal server.*"
    
    payload = {
        "username": "Signal Seeker Hunter",
        "embeds": [{
            "title": "🔥 REAL TRADERS IN PAIN - GENUINE LEADS 🔥",
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
    
    # Run both engines
    hn_leads = scan_hackernews()
    reddit_leads = scan_reddit_proxy()
    
    # Combine and sort
    all_leads = hn_leads + reddit_leads
    all_leads.sort(key=lambda x: x['pain_score'], reverse=True)
    
    # Filter duplicates
    new_leads = [l for l in all_leads if l['id'] not in already_sent]
    
    print(f"📊 Total found: {len(all_leads)}, New leads: {len(new_leads)}")
    
    if new_leads:
        print(f"🎉 Found {len(new_leads)} NEW people in pain!")
        send_to_discord(new_leads)
        for l in new_leads:
            already_sent.add(l['id'])
    
    save_sent_seeks(already_sent)
    print("💾 State saved.")