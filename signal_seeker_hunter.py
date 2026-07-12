import requests
import os
import json
import re
import xml.etree.ElementTree as ET

# --- CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.getenv("SIGNAL_HUNTER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")
STATE_FILE = "sent_signal_seeks.json"

# Bitcointalk RSS Feeds (Public and Unblockable)
# Board 5 = Speculation (Where people gamble and lose)
# Board 6 = Altcoins (Where people get rug pulled)
RSS_FEEDS = [
    "https://bitcointalk.org/index.php?type=rss;action=.xml;board=5.0",
    "https://bitcointalk.org/index.php?type=rss;action=.xml;board=6.0"
]

# Keywords that indicate someone is in pain or needs help
PAIN_KEYWORDS = [
    "scam", "rug", "rugpull", "dev sold", "dumped", "fake", 
    "honeypot", "stuck", "lost", "rekt", "help", "recovery",
    "drained", "phishing", "hack", "stolen"
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
    # ALWAYS save the file, even if empty, to prevent git errors
    recent_urls = list(sent_set)[-300:]
    with open(STATE_FILE, 'w') as f:
        json.dump(recent_urls, f)

def clean_html(raw_html):
    """Removes HTML tags from the RSS description."""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def scan_bitcointalk():
    print("🕵️‍♂️ Scanning Bitcointalk for traders in pain...")
    found_leads = []
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignalHunter/1.0'}
    
    for feed_url in RSS_FEEDS:
        try:
            response = requests.get(feed_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Parse the XML RSS feed
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            
            for item in items:
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                desc_raw = item.find('description').text if item.find('description') is not None else ""
                
                # Clean the description text
                desc = clean_html(desc_raw).lower()
                title_lower = title.lower()
                full_text = f"{title_lower} {desc}"
                
                # Check for pain keywords
                matches = [kw for kw in PAIN_KEYWORDS if kw in full_text]
                
                if len(matches) >= 1:
                    snippet = desc[:150].strip()
                    if len(desc) > 150:
                        snippet += "..."
                        
                    found_leads.append({
                        'title': title,
                        'url': link,
                        'snippet': snippet,
                        'pain_score': len(matches),
                        'matches': ", ".join(matches)
                    })
                    
        except Exception as e:
            print(f"⚠️ Error scanning feed {feed_url}: {e}")
            continue
            
    # Sort by pain score (most desperate first)
    found_leads.sort(key=lambda x: x['pain_score'], reverse=True)
    return found_leads

def send_to_discord(leads):
    if not leads:
        print("No new leads found this cycle.")
        return
        
    description = "*Crypto traders in distress from Bitcointalk. High-intent leads for your signals.*\n\n"
    
    for lead in leads[:5]:
        description += f"🚨 **[{lead['title']}]({lead['url']})**\n"
        description += f"📉 *Pain Score: {lead['pain_score']}* | Keywords: `{lead['matches']}`\n"
        description += f"> {lead['snippet']}\n\n"
        
    description += "💡 *Strategy: Reply with empathy and a free tip, then drop your server link.*"
    
    payload = {
        "username": "Signal Seeker Hunter",
        "embeds": [{
            "title": "🔥 CRYPTO TRADERS IN PAIN - HOT LEADS 🔥",
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
    all_leads = scan_bitcointalk()
    new_leads = [l for l in all_leads if l['url'] not in already_sent]
    
    if new_leads:
        print(f"🎉 Found {len(new_leads)} NEW leads!")
        send_to_discord(new_leads)
        for l in new_leads:
            already_sent.add(l['url'])
    
    # ALWAYS save state to prevent the "file not found" git error
    save_sent_seeks(already_sent)
    print("💾 State saved.")