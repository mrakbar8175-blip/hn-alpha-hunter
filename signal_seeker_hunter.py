import requests
import os
import json
import re

DISCORD_WEBHOOK_URL = os.getenv("SIGNAL_HUNTER_WEBHOOK", "PASTE_YOUR_WEBHOOK_HERE")
STATE_FILE = "sent_signal_seeks.json"

# More keywords, more common phrases
PAIN_KEYWORDS = [
    "lost", "rekt", "liquidated", "help", "struggling", "losing", 
    "scam", "rug", "fake", "broke", "confused", "giving up", 
    "quit", "worst", "huge loss", "fuck", "done", "never",
    "dumped", "crashed", "down", "bleeding", "stuck", "trapped",
    "panic", "sell", "selling", "afraid", "scared", "worried"
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
        
        print(f"📊 Found {len(threads_data)} pages of threads")
        
        # Scan first 3 pages (more threads)
        for page in threads_data[:3]:
            threads = page.get('threads', [])
            print(f"📄 Scanning {len(threads)} threads on this page")
            
            for thread in threads[:15]:  # Check 15 threads per page
                thread_no = thread.get('no')
                thread_url = f"https://a.4cdn.org/biz/thread/{thread_no}.json"
                
                try:
                    thread_response = requests.get(thread_url, headers=headers, timeout=10)
                    
                    if thread_response.status_code != 200:
                        continue
                        
                    thread_data = thread_response.json()
                    posts = thread_data.get('posts', [])
                    
                    # Check first 30 posts per thread
                    for post in posts[:30]:
                        comment = post.get('com', '')
                        
                        # Skip if no comment
                        if not comment:
                            continue
                            
                        post_no = post.get('no')
                        
                        # Remove HTML tags and convert to lowercase
                        comment_clean = re.sub('<[^<]+?>', '', comment).lower()
                        
                        # Check for pain keywords
                        matches = [kw for kw in PAIN_KEYWORDS if kw in comment_clean]
                        
                        # LOWERED THRESHOLD: Just 1 match now (was 2)
                        if len(matches) >= 1:
                            snippet = comment_clean[:200]
                            if len(comment_clean) > 200:
                                snippet += "..."
                            
                            found_leads.append({
                                'post_no': post_no,
                                'thread_no': thread_no,
                                'comment': snippet,
                                'url': f"https://boards.4channel.org/biz/thread/{thread_no}#p{post_no}",
                                'pain_score': len(matches),
                                'matches': ", ".join(matches[:5])
                            })
                except Exception as e:
                    continue
                        
    except Exception as e:
        print(f"❌ Error scanning 4chan: {e}")
    
    print(f"🔍 Found {len(found_leads)} total posts with pain keywords")
    
    # Sort by pain score
    found_leads.sort(key=lambda x: x['pain_score'], reverse=True)
    return found_leads

def send_to_discord(leads):
    if not leads:
        print("❌ No new people in pain found.")
        return
        
    description = "*REAL TRADERS on 4chan /biz/ struggling with crypto. Reply with value, then mention your server.*\n\n"
    
    for lead in leads[:10]:  # Show top 10
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
    
    print(f"📊 Total leads: {len(all_leads)}, New leads: {len(new_leads)}")
    
    if new_leads:
        print(f"🎉 Found {len(new_leads)} NEW people in pain!")
        send_to_discord(new_leads)
        for l in new_leads:
            already_sent.add(l['url'])
    
    save_sent_seeks(already_sent)
    print("💾 State saved.")