import requests
import os
import re
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
SENT_IDS_FILE = Path("sent_tools.json")

KEYWORDS = ["ai", "gpt", "saas", "tool", "show hn", "startup", "agent", "automation"]
COMPILED_KEYWORDS = [re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) for kw in KEYWORDS]

TOP_STORIES_LIMIT = 500


def load_sent_ids():
    """Return set of previously sent story IDs as strings."""
    if not SENT_IDS_FILE.exists():
        print("📁 No sent_ids file found. Starting fresh.")
        return set()
    try:
        with open(SENT_IDS_FILE, "r") as f:
            data = json.load(f)
            # Force all IDs to be strings
            ids = {str(i) for i in data}
            print(f"📋 Loaded {len(ids)} previously sent IDs.")
            return ids
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Could not read sent_ids file ({e}). Starting fresh.")
        return set()


def save_sent_ids(ids):
    """Save set of string IDs to JSON."""
    try:
        with open(SENT_IDS_FILE, "w") as f:
            json.dump(list(ids), f)
        print(f"💾 Saved {len(ids)} IDs to {SENT_IDS_FILE}")
    except IOError as e:
        print(f"❌ CRITICAL: Failed to save sent IDs: {e}")
        print("   Duplicates may occur on the next run.")


def fetch_item(story_id):
    """Fetch a single HN item."""
    try:
        item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        response = requests.get(item_url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error fetching item {story_id}: {e}")
        return None


def get_top_tech_stories(sent_ids):
    """
    Fetch top HN stories, skip already‑sent ones,
    return new matching stories sorted by score.
    """
    print(f"🕵️  Scanning top {TOP_STORIES_LIMIT} stories for AI & SaaS tools...")
    top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"

    try:
        response = requests.get(top_url, timeout=5)
        response.raise_for_status()
        story_ids = response.json()[:TOP_STORIES_LIMIT]
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch top stories: {e}")
        return []

    found_tools = []

    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_id = {executor.submit(fetch_item, sid): sid for sid in story_ids}

        for future in as_completed(future_to_id):
            item = future.result()
            if not item:
                continue

            story_id = str(item.get('id'))        # always string
            title = item.get('title')
            if not title:
                continue

            if story_id in sent_ids:
                print(f"⏭️  Skipping already‑sent: {story_id} – {title}")
                continue

            if any(pattern.search(title) for pattern in COMPILED_KEYWORDS):
                found_tools.append({
                    'id': story_id,
                    'title': title,
                    'url': item.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                    'score': item.get('score', 0)
                })

    print(f"🔍 Found {len(found_tools)} new matching stories (after dedup).")
    found_tools.sort(key=lambda x: x['score'], reverse=True)
    return found_tools


def send_to_discord(tools, sent_ids):
    """
    Send top‑5 tools to Discord, but **only** if their ID is not already sent.
    Returns IDs of successfully sent stories.
    """
    # Final safety filter (just in case)
    truly_new = [t for t in tools if t['id'] not in sent_ids]
    if len(truly_new) < len(tools):
        print(f"⚠️  {len(tools) - len(truly_new)} tools were already sent. Removed.")

    if not truly_new:
        print("No new tools to send (all were already sent).")
        return set()

    to_send = truly_new[:5]
    print(f"📤 Preparing to send {len(to_send)} tools to Discord...")

    description = "*Found on Hacker News. Get them before everyone else!*\n\n"
    for tool in to_send:
        description += f"🔹 **[{tool['title']}]({tool['url']})**\n"
        description += f"⭐ Community Score: {tool['score']}\n\n"
    description += "💡 *Want early access to more tools? DM the admin.*"

    payload = {
        "username": "AI Tool Hunter",
        "embeds": [{
            "title": "🚀 TOP NEW AI & SAAS TOOLS TODAY 🚀",
            "description": description,
            "color": 5814783
        }]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Alerts sent to Discord!")
        return {tool['id'] for tool in to_send}
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send to Discord: {e}")
        return set()


if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL.startswith("PASTE_YOUR"):
        print("❌ Discord webhook URL not configured.")
        print("   Set DISCORD_WEBHOOK_URL environment variable or edit the script.")
        exit(1)

    sent_ids = load_sent_ids()
    new_tools = get_top_tech_stories(sent_ids)

    # Pass sent_ids to the sending function for a last‑chance dedup check
    newly_sent = send_to_discord(new_tools, sent_ids)

    if newly_sent:
        sent_ids.update(newly_sent)
        save_sent_ids(sent_ids)
    else:
        print("ℹ️  Nothing new was sent. ID file unchanged.")