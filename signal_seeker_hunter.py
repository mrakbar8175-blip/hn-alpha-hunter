import requests
import os
import json
import re

DISCORD_WEBHOOK_URL = os.getenv("SIGNAL_HUNTER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")
STATE_FILE = "sent_signal_seeks.json"

# Search for PAIN directly in HN comments
PAIN_SEARCHES = [
    "lost money",
    "got rekt", 
    "liquidated",
    "scammed",
    "bad signal",
    "fake signal",
    "lost everything",
    "trading loss",
    "crypto loss"
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

def search_hn_for_pain(query):
    """Search HN comments for a specific pain phrase."""
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": query,
        "tags": "comment",
        "hitsPerPage": 30
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get('hits', [])
    except Exception as e:
        print(f"⚠️ Search failed for '{query}': {e}")
        return []

def scan_hackernews():
    """Search HN for people in pain using multiple queries."""
    print("🕵️‍♂️ Scanning Hacker News for traders in pain...")
    found_leads = []
    seen_ids = set()
    
    for pain_query in PAIN_SEARCHES:
        print(f"  🔍 Searching: {pain_query}")
        hits = search_hn_for_pain(pain_query)
        
        for hit in hits:
            object_id = hit.get('objectID')
            
            # Skip duplicates
            if object_id in seen_ids:
                continue
            seen_ids.add(object_id)
            
            comment_text = hit.get('comment_text', '')
            # Remove HTML tags
            comment_clean = re.sub('<[^<]+?>', '', comment_text)
            
            author = hit.get('author', 'Unknown')
            story_title = hit.get('story_title', 'Unknown')
            
            snippet = comment_clean[:200]
            if len(comment_clean) > 200:
                snippet += "..."
                
            found_leads.append({
                'author': author,
                'title': f"Re: {story_title}",
                'snippet': snippet,
                'url': f"https://news.ycombinator.com/item?id={object_id}",
                'id': object_id,
                'query': pain_query
            })
    
    print(f"📊 Found {len(found_leads)} total comments with pain")
    return found_leads

def send_to_discord(leads):
    if not leads:
        print("❌ No new people in pain found.")
        return
        
    description = "*REAL PEOPLE on Hacker News struggling with crypto/trading. Reply with value, then mention your server.*\n\n"
    
    for lead in leads[:10]:
        description += f"👤 **{lead['author']}**\n"
        description += f"📝 **{lead['title']}**\n"
        description += f"💬 > {lead['snippet']}\n"
        description += f"🔗 [Reply Here]({lead['url']}) | Search: `{lead['query']}`\n\n"
        
    description += "💡 *Strategy: Reply with empathy + free tip, then softly mention your signal server.*"
    
    payload = {
        "username": "Signal Seeker Hunter",
        "embeds": [{
            "title": "🔥 REAL TRADERS IN PAIN - HACKER NEWS 🔥",
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
    all_leads = scan_hackernews()
    
    # Filter duplicates and already-sent
    new_leads = [l for l in all_leads if l['id'] not in already_sent]
    
    print(f"📊 Total found: {len(all_leads)}, New leads: {len(new_leads)}")
    
    if new_leads:
        print(f"🎉 Found {len(new_leads)} NEW people in pain!")
        send_to_discord(new_leads)
        for l in new_leads:
            already_sent.add(l['id'])
    
    save_sent_seeks(already_sent)
    print("💾 State saved.")