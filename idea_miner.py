import requests
import os
import json
from pathlib import Path

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("IDEA_MINER_WEBHOOK", "")

# File to persist already sent post IDs
SENT_IDS_FILE = Path("sent_ideas.json")

# Algolia HN Search API endpoint
API_URL = "https://hn.algolia.com/api/v1/search"

# Pain-point phrases
PAIN_PHRASES = [
    "is there a", "looking for", "alternative to", "how do you",
    "recommend a", "tool for", "software for", "frustrated with", "manual"
]


def load_sent_ids():
    """Load previously sent post IDs from a JSON file."""
    if not SENT_IDS_FILE.exists():
        return set()
    try:
        with open(SENT_IDS_FILE, "r") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, IOError):
        print("⚠️ Could not read sent IDs file. Starting fresh.")
        return set()


def save_sent_ids(ids):
    """Save the set of sent post IDs to a JSON file."""
    try:
        with open(SENT_IDS_FILE, "w") as f:
            json.dump(list(ids), f)
    except IOError as e:
        print(f"❌ Failed to save sent IDs: {e}")


def get_ask_hn_ideas(sent_ids):
    """Fetch Ask HN ideas, exclude already sent posts, return new ones sorted by points."""
    print("🕵️‍♂️ Mining Hacker News 'Ask HN' for startup ideas...")
    found_ideas = []

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
        post_id = post.get('objectID')
        title = post.get('title', '')

        # Skip if we already sent this one
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

    # Sort by points descending
    found_ideas.sort(key=lambda x: x['points'], reverse=True)
    return found_ideas


def send_to_discord(ideas):
    """Send the top 5 ideas to Discord, return IDs of successfully sent posts."""
    if not ideas:
        print("No new pain points found today.")
        return set()

    # Prepare the embed description
    description = "*Raw business problems and questions from Hacker News. Build a solution for these!*\n\n"

    for idea in ideas[:5]:  # top 5
        description += f"🚨 **[{idea['title']}]({idea['url']})**\n"
        description += f"⬆️ {idea['points']} points | 💬 {idea['comments']} comments\n\n"

    description += "💡 *See a problem you can solve? Jump into the comments or build it!*"

    payload = {
        "username": "The Idea Miner",
        "embeds": [{
            "title": "💡 DAILY STARTUP IDEAS & PAIN POINTS 💡",
            "description": description,
            "color": 15105570  # Orange/gold
        }]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Ideas sent to Discord!")
        # Return IDs of the ones we actually sent (top 5)
        return {idea['id'] for idea in ideas[:5]}
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")
        return set()


if __name__ == "__main__":
    # Validate webhook URL
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL == "PASTE_YOUR_WEBHOOK_HERE":
        print("❌ Discord webhook URL not configured. Set the IDEA_MINER_WEBHOOK environment variable.")
        exit(1)

    # Load previously sent IDs
    sent_ids = load_sent_ids()

    # Get new ideas (excluding already sent ones)
    new_ideas = get_ask_hn_ideas(sent_ids)

    # Send them and get the IDs of those successfully posted
    newly_sent_ids = send_to_discord(new_ideas)

    # Update the persistent store only if we sent something
    if newly_sent_ids:
        sent_ids.update(newly_sent_ids)
        save_sent_ids(sent_ids)
        print(f"📌 Added {len(newly_sent_ids)} new IDs to sent history.")
    else:
        print("No new IDs to record.")