import requests
import os
import re

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("BOUNTY_HUNTER_WEBHOOK", "PASTE_YOUR_BOUNTY_WEBHOOK_HERE")

def get_github_bounties():
    print("💰 Hunting for open GitHub bounties...")
    
    # We use GitHub's public search API to find open issues with 'bounty' or 'reward' labels
    url = "https://api.github.com/search/issues"
    params = {
        "q": "label:bounty OR label:reward state:open",
        "sort": "created",
        "order": "desc",
        "per_page": 15 # Get the 15 newest bounties
    }
    
    # A User-Agent is required by GitHub's API
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
        # GitHub's search API sometimes mixes Pull Requests with Issues. We only want Issues.
        if 'pull_request' in item:
            continue
            
        title = item.get('title', '')
        html_url = item.get('html_url', '')
        
        # Extract the repository name from the API URL
        repo_url = item.get('repository_url', '')
        repo_name = repo_url.split('/')[-1] if repo_url else "Unknown Repo"
        
        # Try to extract the dollar amount from the title (e.g., "$100", "$1,500")
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
    
    for bounty in bounties[:5]: # Send top 5 newest bounties
        description += f"💰 **[{bounty['amount']}]({bounty['url']})** - {bounty['title']}\n"
        description += f"📦 *Repo: {bounty['repo']}*\n\n"
        
    description += "💡 *See a bounty you can fix? Jump into the issue and claim it!*"
    
    payload = {
        "username": "The Bounty Hunter",
        "embeds": [{
            "title": "💸 FRESH GITHUB BOUNTIES AVAILABLE 💸",
            "description": description,
            "color": 3066993 # A nice money green color
        }]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Bounties sent to Discord!")
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")

if __name__ == "__main__":
    bounties = get_github_bounties()
    send_to_discord(bounties)