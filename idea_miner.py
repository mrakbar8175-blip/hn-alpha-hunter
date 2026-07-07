import requests
import os

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("IDEA_MINER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")

# We use the Algolia HN Search API. It's free, official, and unblockable.
API_URL = "https://hn.algolia.com/api/v1/search"

# Phrases that indicate a pain point or a request for a tool
# Since these are full phrases, we don't even need complex Regex!
PAIN_PHRASES = [
    "is there a", "looking for", "alternative to", "how do you", 
    "recommend a", "tool for", "software for", "frustrated with", "manual"
]

def get_ask_hn_ideas():
    print("🕵️‍♂️ Mining Hacker News 'Ask HN' for startup ideas...")
    found_ideas = []
    
    # We fetch the 50 most recent "Ask HN" posts
    params = {
        "query": "Ask HN",
        "tags": "ask_hn",
        "hitsPerPage": 50
    }
    
    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        posts = response.json().get('hits', [])
    except Exception as e:
        print(f"❌ Error fetching Ask HN: {e}")
        return []
        
    for post in posts:
        title = post.get('title', '')
        
        # Check if the title contains any of our pain-point phrases
        if any(phrase in title.lower() for phrase in PAIN_PHRASES):
            found_ideas.append({
                'title': title,
                'url': f"https://news.ycombinator.com/item?id={post.get('objectID')}",
                'points': post.get('points', 0),
                'comments': post.get('num_comments', 0)
            })
            
    # Sort by points (upvotes) so the best ideas show first
    found_ideas.sort(key=lambda x: x['points'], reverse=True)
    return found_ideas

def send_to_discord(ideas):
    if not ideas:
        print("No new pain points found today.")
        return
        
    description = "*Raw business problems and questions from Hacker News. Build a solution for these!*\n\n"
    
    for idea in ideas[:5]: # Send top 5 ideas
        description += f"🚨 **[{idea['title']}]({idea['url']})**\n"
        description += f"⬆️ {idea['points']} points | 💬 {idea['comments']} comments\n\n"
        
    description += "💡 *See a problem you can solve? Jump into the comments or build it!*"
    
    payload = {
        "username": "The Idea Miner",
        "embeds": [{
            "title": "💡 DAILY STARTUP IDEAS & PAIN POINTS 💡",
            "description": description,
            "color": 15105570 # Orange/gold color
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Ideas sent to Discord!")
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")

if __name__ == "__main__":
    ideas = get_ask_hn_ideas()
    send_to_discord(ideas)