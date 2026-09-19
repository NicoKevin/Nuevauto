## Explain how DataDome detects my browser

DataDome is a sophisticated "Bot Protection" service that detects your browser using a multi-layered approach. It doesn't just look for one thing; it correlates hundreds of signals to build a "trust score."

Here is how it likely detects and analyzes your browser on this specific page:

1. Browser Fingerprinting (The "Static" Check)
DataDome collects specific technical attributes that are hard to spoof perfectly:

Canvas & WebGL Fingerprinting: It asks your browser to render a hidden image. The way your specific hardware (GPU) and software (drivers) render pixels is unique.
Audio Fingerprinting: It analyzes how your browser processes audio signals.
Font Enumeration: It checks which system fonts you have installed.
2. Environment Inconsistencies (The "Liar" Check)
Bots often try to hide their identity, but DataDome looks for "leaks":

navigator.webdriver: It checks if this is true (indicating automation tools like Selenium or Puppeteer).
Feature Mismatches: If your User-Agent says you are on a Mac, but your navigator.platform says Win32, or if you claim to be Chrome but lack specific Chrome-only APIs (like window.chrome), you are flagged.
Screen vs. Window: It checks if your screen resolution matches your window size in a way that makes sense for a human user.
3. Behavioral Analysis (The "Human" Check)
DataDome tracks how you interact with the page in real-time:

Mouse Movement: Humans move in irregular, curved paths with varying speeds. Bots often move in perfectly straight lines or jump instantly between coordinates.
Keystroke Dynamics: The timing between key presses (flight time) is unique to humans.
Scroll Patterns: Bots tend to scroll to specific elements instantly; humans scroll incrementally as they read.
4. Network and Header Analysis
TLS Fingerprinting (JA3): DataDome looks at how your browser initiates a secure (HTTPS) connection. Every browser (Chrome, Firefox, Safari) has a unique "handshake" signature.
HTTP/2 Signals: It checks if the header order and compression match a real browser's behavior.
IP Reputation: It checks if your IP belongs to a residential provider (like Orange, Free) or a data center (like AWS, Google Cloud). Data center IPs are almost always blocked or challenged.
5. The DataDome Cookie
In your environment, we found the datadome cookie. This cookie contains an encrypted token.

Every time you perform a sensitive action (like clicking "Voir le numéro"), this token is sent to DataDome's servers.
If your browser fails any of the checks above, DataDome instructs the Leboncoin server to block the request or present a CAPTCHA (often the Geetest or a custom sliding puzzle).
In short: DataDome isn't just looking at who you say you are (User-Agent), it's looking at how your machine behaves and if your hardware "talks" exactly like a real Chrome browser on a real Windows machine should.


## Can you find the specific DataDome script on this page? What happens to the network requests when I click the button? How can I check if my browser is leaking 'webdriver' status?

1. The DataDome Script
On this page, DataDome is integrated using two methods to ensure it's hard to bypass:

External Script: https://dd.leboncoin.fr/tags.js. This is the main engine. It's hosted on a subdomain of leboncoin.fr to make it look like "first-party" code, which helps bypass some simple tracking blockers.
Inline Initialization: There is an inline script (uid found in the scan) that initializes the protection:

!(function (a, b, c, d, e, f) {
  a.ddjskey = e; // The unique public key for Leboncoin
  a.ddoptions = f || null;
  // ... logic to inject tags.js dynamically
})(window, document, "script", "https://dd.leboncoin.fr/tags.js", "9451433F53109E964F86877484B639")

2. Network Requests when clicking "Voir le numéro"
When you click that button, several things happen in the background:

Anti-Bot Verification: The DataDome script immediately analyzes your current "session state." It checks if your datadome cookie is still valid and if your recent behavior (mouse movement, timing) is suspicious.
The API Call: If you are deemed "human," the browser sends a POST or GET request to: https://api.leboncoin.fr/adview/v4/phone/{ad_id}
Encrypted Payload: The request usually includes custom headers (like X-Device-Id or a DataDome-specific header) and the current DataDome token.
The Response:
Success: You receive a JSON object: {"phone": "0612345678"}.
Failure (Bot detected): You receive a 403 Forbidden response. The response body often contains a url pointing to a CAPTCHA page (e.g., https://geo.captcha-delivery.com/...).
Failure (Not logged in): You receive a 401 Unauthorized or a redirect to the login flow.
3. Checking for webdriver Leaks
The navigator.webdriver property is the most common way bots are caught. You can check it yourself right now:

Open the Console tab in DevTools.
Type navigator.webdriver and press Enter.
If it returns false, your current browser is "clean."
If it returns true, you are using an automated browser, and DataDome will likely block you.
Advanced Tip: Even if navigator.webdriver is false, DataDome can detect modern automation (like Playwright or Puppeteer) by looking for hidden variables like window.__playwright, window.__selenium_evaluate, or by checking if navigator.plugins.length is 0 (which is rare for a real human browser).
