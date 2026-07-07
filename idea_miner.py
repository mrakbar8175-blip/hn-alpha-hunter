import requests
import os
import json
from pathlib import Path

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("IDEA_MINER_WEBHOOK", "")

# File to persist already‑sent post IDs (restored via GitHub artifact)
SENT_IDS_FILE = Path("sent_ideas.json")

# HN Search API – date‑sorted endpoint (newest first)
API_URL = "https://hn.algolia.com/api/v1/search_by_date"

# Pain‑point phrases (simple substring matching)
PAIN_PHRASES = [
    "is there a", "looking for", "alternative to", "how do you",
    "recommend a", "tool for", "software for", "frustrated with", "manual"
]

MAX_HITS = 200  # fetch up to 200 recent Ask HN posts


def load_sent_ids():
    """Load previously sent post IDs from a JSON file."""
    if not SENT_IDS_FILE.exists():
        print("📁 No sent_ids file found. Starting fresh.")
        return set()
    try:
        with open(SENT_IDS_FILE, "r") as f:
            data = json.load(f)
            ids = {str(i) for i in data}
            print(f"📋 Loaded {len(ids)} previously sent IDs.")
            return ids
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Could not read sent_ids file ({e}). Starting fresh.")
        return set()


def save_sent_ids(ids):
    """Save the set of sent IDs to the JSON file."""
    try:
        with open(SENT_IDS_FILE, "w") as f:
            json.dump(list(ids), f)
        print(f"💾 Saved {len(ids)} IDs to {SENT_IDS_FILE}")
    except IOError as e:
        print(f"❌ CRITICAL: Failed to save sent IDs: {e}")
        print("   Duplicates may occur on next run.")


def get_ask_hn_ideas(sent_ids):
    """Fetch recent Ask HN posts, exclude already‑sent ones, and return new pain‑point ideas."""
    print(f"🕵️  Mining up to {MAX_HITS} recent Ask HN posts...")
    found_ideas = []

    params = {
        "tags": "ask_hn",          # only Ask HN
        "query": "Ask HN",         # optional, refines results
        "hitsPerPage": MAX_HITS    # no sort_by_date needed – endpoint sorts by date desc
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
        post_id = str(post.get('objectID'))
        title = post.get('title', '')

        # Skip if already sent
        if post_id in sent_ids:
            continue

        # Check if title contains a pain‑point phrase
        if any(phrase in title.lower() for phrase in PAIN_PHRASES):
            found_ideas.append({
                'id': post_id,
                'title': title,
                'url': f"https://news.ycombinator.com/item?id={post_id}",
                'points': post.get('points', 0),
                'comments': post.get('num_comments', 0)
            })

    print(f"🔍 Found {len(found_ideas)} new pain‑point posts (after dedup).")
    # Sort by upvotes (most validated problem first)
    found_ideas.sort(key=lambda x: x['points'], reverse=True)
    return found_ideas


def send_to_discord(ideas):
    """Send up to 5 ideas to Discord. Returns set of successfully sent IDs."""
    if not ideas:
        print("No new ideas to send.")
        return set()

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
            "color": 15105570  # orange/gold
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
    # Validate webhook URL
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL.startswith("PASTE_YOUR"):
        print("❌ Discord webhook URL not configured.")
        print("   Set the IDEA_MINER_WEBHOOK environment variable or edit the script.")
        exit(1)

    # 1. Load previously sent IDs (restored from artifact)
    sent_ids = load_sent_ids()

    # 2. Fetch new ideas, excluding those already sent
    new_ideas = get_ask_hn_ideas(sent_ids)

    # 3. Send to Discord and collect IDs of successfully sent posts
    newly_sent = send_to_discord(new_ideas)

    # 4. Update persistent store only if something was sent
    if newly_sent:
        sent_ids.update(newly_sent)
        save_sent_ids(sent_ids)
    else:
        print("ℹ️  Nothing new was sent. ID file unchanged.")