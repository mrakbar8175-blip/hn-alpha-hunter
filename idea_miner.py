import requests
import os
import json
from pathlib import Path

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("IDEA_MINER_WEBHOOK", "")
SENT_IDS_FILE = Path("sent_ideas.json")
API_URL = "https://hn.algolia.com/api/v1/search"

PAIN_PHRASES = [
    "is there a", "looking for", "alternative to", "how do you",
    "recommend a", "tool for", "software for", "frustrated with", "manual"
]

# We'll fetch a larger set to offset the "already sent" filter
MAX_HITS = 200  # Algolia allows up to 1000


def load_sent_ids():
    """Load previously sent post IDs from JSON. Returns a set of strings."""
    if not SENT_IDS_FILE.exists():
        print("📁 No sent_ids file found. Starting fresh.")
        return set()
    try:
        with open(SENT_IDS_FILE, "r") as f:
            data = json.load(f)
            # Ensure all are strings
            ids = {str(i) for i in data}
            print(f"📋 Loaded {len(ids)} previously sent IDs.")
            return ids
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Could not read sent_ids file ({e}). Starting fresh.")
        return set()


def save_sent_ids(ids):
    """Save the set of sent IDs to JSON."""
    try:
        with open(SENT_IDS_FILE, "w") as f:
            json.dump(list(ids), f)
        print(f"💾 Saved {len(ids)} IDs to {SENT_IDS_FILE}")
    except IOError as e:
        print(f"❌ CRITICAL: Failed to save sent IDs: {e}")
        print("   The same posts may be sent again on the next run.")


def get_ask_hn_ideas(sent_ids):
    """
    Fetch recent Ask HN posts, filter out already-sent IDs,
    and return new pain-point ideas sorted by upvotes.
    """
    print(f"🕵️  Mining up to {MAX_HITS} Ask HN posts...")
    found_ideas = []

    params = {
        "query": "Ask HN",
        "tags": "ask_hn",
        "hitsPerPage": MAX_HITS
    }

    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        posts = response.json().get('hits', [])
        print(f"📡 Received {len(posts)} posts from API.")
    except Exception as e:
        print(f"❌ Error fetching Ask HN: {e}")
        return []

    for post in posts:
        post_id = str(post.get('objectID'))   # always string
        title = post.get('title', '')

        if post_id in sent_ids:
            continue

        if any(phrase in title.lower() for phrase in PAIN_PHRASES):
            found_ideas.append({
                'id': post_id,
                'title': title,
                'url': f"https://news.ycombinator.com/item?id={post_id}",
                'points': post.get('points', 0),
                'comments': post.get('num_comments', 0)
            })

    print(f"🔍 Found {len(found_ideas)} new pain-point posts (after excluding already sent).")
    found_ideas.sort(key=lambda x: x['points'], reverse=True)
    return found_ideas


def send_to_discord(ideas):
    """Send up to 5 ideas to Discord. Returns set of successfully sent IDs."""
    if not ideas:
        print("No new ideas to send.")
        return set()

    # Take at most 5
    to_send = ideas[:5]
    print(f"📤 Preparing to send {len(to_send)} ideas to Discord...")

    description = "*Raw business problems and questions from Hacker News. Build a solution for these!*\n\n"
    for idea in to_send:
        description += f"🚨 **[{idea['title']}]({idea['url']})**\n"
        description += f"⬆️ {idea['points']} points | 💬 {idea['comments']} comments\n\n"
    description += "💡 *See a problem you can solve? Jump into the comments or build it!*"

    payload = {
        "username": "The Idea Miner",
        "embeds": [{
            "title": "💡 DAILY STARTUP IDEAS & PAIN POINTS 💡",
            "description": description,
            "color": 15105570
        }]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Ideas sent to Discord!")
        return {idea['id'] for idea in to_send}
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")
        return set()


if __name__ == "__main__":
    # 1. Validate webhook
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL.startswith("PASTE_YOUR"):
        print("❌ Discord webhook URL not configured.")
        print("   Set IDEA_MINER_WEBHOOK environment variable or edit the script.")
        exit(1)

    # 2. Load past sent IDs
    sent_ids = load_sent_ids()

    # 3. Fetch new ideas
    new_ideas = get_ask_hn_ideas(sent_ids)

    # 4. Send and collect IDs of successfully sent posts
    newly_sent = send_to_discord(new_ideas)

    # 5. Update persistent store ONLY if something was sent
    if newly_sent:
        sent_ids.update(newly_sent)
        save_sent_ids(sent_ids)
    else:
        print("ℹ️  Nothing new was sent. ID file unchanged.")