import requests
import os
import re
import json

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("BOUNTY_HUNTER_WEBHOOK", "PASTE_YOUR_BOUNTY_WEBHOOK_HERE")
STATE_FILE = "sent_bounties.json"

def load_sent_bounties():
    """Loads the memory file to see what we already posted."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_sent_bounties(sent_set):
    """Saves the memory file. Keeps only the last 200 so it doesn't get too huge."""
    recent_urls = list(sent_set)[-200:]
    with open(STATE_FILE, 'w') as f:
        json.dump(recent_urls, f)

def get_github_bounties():
    print("💰 Hunting for open GitHub bounties...")
    
    url = "https://api.github.com/search/issues"
    # FIXED: Changed 'state:open' to 'is:open' and searched the title directly!
    params = {
        "q": "is:issue is:open bounty in:title",
        "sort": "created",
        "order": "desc",
        "per_page": 30 # Fetch a bit more to ensure we find new ones
    }
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "BountyHunterBot/1.0"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        items = response.json().get('items', [])
    except Exception as e:
        print(f"❌ Error fetching bounties: {e}")
        return []
        
    found_bounties = []
    
    for item in items:
        if 'pull_request' in item:
            continue
            
        title = item.get('title', '')
        html_url = item.get('html_url', '')
        repo_url = item.get('repository_url', '')
        repo_name = repo_url.split('/')[-1] if repo_url else "Unknown Repo"
        
        amount_match = re.search(r'\$[\d,]+', title)
        amount = amount_match.group(0) if amount_match else "Hidden/Contact"
        
        found_bounties.append({
            'title': title,
            'url': html_url,
            'repo': repo_name,
            'amount': amount
        })
        
    return found_bounties

def send_to_discord(bounties):
    if not bounties:
        print("No new bounties found today.")
        return
        
    description = "*Fresh, open bounties on GitHub. Claim them and get paid!*\n\n"
    
    for bounty in bounties[:5]:
        description += f"💰 **[{bounty['amount']}]({bounty['url']})** - {bounty['title']}\n"
        description += f"📦 *Repo: {bounty['repo']}*\n\n"
        
    description += "💡 *See a bounty you can fix? Jump into the issue and claim it!*"
    
    payload = {
        "username": "The Bounty Hunter",
        "embeds": [{
            "title": "💸 FRESH GITHUB BOUNTIES AVAILABLE 💸",
            "description": description,
            "color": 3066993
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Bounties sent to Discord!")
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")

if __name__ == "__main__":
    # 1. Load the history of what we already sent
    already_sent = load_sent_bounties()
    
    # 2. Fetch fresh bounties from GitHub
    all_bounties = get_github_bounties()
    
    # 3. Filter out the ones we already sent!
    new_bounties = [b for b in all_bounties if b['url'] not in already_sent]
    
    if new_bounties:
        print(f"🎉 Found {len(new_bounties)} NEW bounties!")
        send_to_discord(new_bounties)
        
        # 4. Add the new URLs to our memory and save it
        for b in new_bounties:
            already_sent.add(b['url'])
        save_sent_bounties(already_sent)
        print("💾 Saved state to prevent duplicates next time.")
    else:
        print("No new bounties found today (already sent the ones that are open).")