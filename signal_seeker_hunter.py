import requests
import os
import json
import re

DISCORD_WEBHOOK_URL = os.getenv("SIGNAL_HUNTER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")
STATE_FILE = "sent_signal_seeks.json"

PAIN_KEYWORDS = [
    "lost money", "lost all", "got rekt", "rekt", "liquidated",
    "need help", "help me", "struggling", "losing money", "down bad",
    "scammed", "rug pull", "fake signals", "bad signals", "lost everything",
    "broke", "don't know what to do", "confused", "selling everything",
    "giving up", "quit trading", "worst trade", "huge loss", "fuck me",
    "fuck this", "done trading", "never again"
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

def scan_4chan_biz():
    print("🕵️‍♂️ Scanning 4chan /biz/ for traders in pain...")
    found_leads = []
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignalHunter/1.0'}
    
    try:
        response = requests.get("https://a.4cdn.org/biz/threads.json", headers=headers, timeout=10)
        response.raise_for_status()
        threads_data = response.json()
        
        for page in threads_data[:2]:
            for thread in page.get('threads', [])[:10]:
                thread_no = thread.get('no')
                thread_url = f"https://a.4cdn.org/biz/thread/{thread_no}.json"
                thread_response = requests.get(thread_url, headers=headers, timeout=10)
                
                if thread_response.status_code != 200:
                    continue
                    
                thread_data = thread_response.json()
                posts = thread_data.get('posts', [])
                
                for post in posts[:20]:
                    comment = post.get('com', '').lower()
                    post_no = post.get('no')
                    comment = re.sub('<[^<]+?>', '', comment)
                    
                    matches = [kw for kw in PAIN_KEYWORDS if kw in comment]
                    
                    if len(matches) >= 2:
                        snippet = comment[:150]
                        if len(comment) > 150:
                            snippet += "..."
                        
                        found_leads.append({
                            'post_no': post_no,
                            'thread_no': thread_no,
                            'comment': snippet,
                            'url': f"https://boards.4channel.org/biz/thread/{thread_no}#p{post_no}",
                            'pain_score': len(matches),
                            'matches': ", ".join(matches[:3])
                        })
                        
    except Exception as e:
        print(f"❌ Error scanning 4chan: {e}")
    
    found_leads.sort(key=lambda x: x['pain_score'], reverse=True)
    return found_leads

def send_to_discord(leads):
    if not leads:
        print("No new people in pain found.")
        return
        
    description = "*REAL TRADERS on 4chan /biz/ struggling with crypto. Reply with value, then mention your server.*\n\n"
    
    for lead in leads[:8]:
        description += f"👤 **Anonymous** | Pain: {'🔴' * lead['pain_score']}\n"
        description += f"💬 > {lead['comment']}\n"
        description += f"🔗 [View Thread]({lead['url']}) | Keywords: `{lead['matches']}`\n\n"
        
    description += "💡 *Strategy: Reply with empathy + free tip, then softly mention your signal server.*"
    
    payload = {
        "username": "Signal Seeker Hunter",
        "embeds": [{
            "title": "🔥 REAL TRADERS IN PAIN - 4CHAN /BIZ/ 🔥",
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
    all_leads = scan_4chan_biz()
    new_leads = [l for l in all_leads if l['url'] not in already_sent]
    
    if new_leads:
        print(f"🎉 Found {len(new_leads)} NEW people in pain!")
        send_to_discord(new_leads)
        for l in new_leads:
            already_sent.add(l['url'])
    
    save_sent_seeks(already_sent)
    print("💾 State saved.")