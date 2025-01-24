"""
This module provides a simple way to authenticate to LinkedIn either by:
  1) Using direct username/password login (via the unofficial linkedin_api library), or
  2) Falling back to existing session cookies from popular web browsers or environment variables.

Key things to know if you need to work with this file:
  • If direct login fails (e.g., challenge or 2FA), we automatically attempt to load cookies from Brave, Chrome, Firefox, or Edge using browser_cookie3.
  • If browser-based cookie retrieval fails, we look for LI_AT and JSESSIONID in the environment (often set via .env).
  • If running on Windows, permission errors or DPAPI encrypt/decrypt issues can arise. In that case, running Python as the same user who browsed LinkedIn or manually copying cookies may be necessary.
  • Make sure to treat all credentials and cookies as sensitive—do not share or commit them to version control without encryption.
"""

from requests.cookies import RequestsCookieJar
from config.secrets import LINKEDIN_EMAIL, LINKEDIN_PASSWORD
from linkedin_api import Linkedin
import browser_cookie3
from config.secrets import LINKEDIN_LI_AT, LINKEDIN_JSESSIONID
import sys
from config.logging_config import setup_logger

logger = setup_logger(__name__)

_INSTANCIATED = {}

def load_linkedin_cookies():
    """
    Tries to load LinkedIn cookies (li_at, JSESSIONID, etc.) from various browsers
    in this order: Brave, Chrome, Firefox, Edge.
    
    If all attempts fail, we fall back to reading them from environment variables
    (like from a .env file), expecting them to be stored as:
        LI_AT=<your li_at cookie>
        JSESSIONID=<your JSESSIONID cookie>
    
    For best results:
      1) Make sure you're running Python as the exact same user that has a 
         logged-in LinkedIn session in the browser you're targeting.
      2) If you run into "RequiresAdminError" or "Failed to decrypt the cipher text 
         with DPAPI", see the user-level vs. admin-level notes from previous discussions.
      3) On Windows + Brave or Chrome, you may need to close the browser or manually
         copy the "Cookies" file to avoid shadowcopy issues. Or, simply store your cookies
         in the .env file as a fallback to bypass these decryption hurdles.
    """
    
    # Browsers to try in order
    browser_methods = [
        browser_cookie3.brave,
        browser_cookie3.chrome,
        browser_cookie3.firefox,
        browser_cookie3.edge,
    ]
    
    for browser_method in browser_methods:
        try:
            cj = browser_method(domain_name='linkedin.com')
            
            # Ensure the returned cookie jar isn't empty or missing critical cookies
            has_li_at = any(cookie.name == "li_at" for cookie in cj)
            has_jsessionid = any(cookie.name.lower() == "jsessionid" for cookie in cj)
            
            if has_li_at and has_jsessionid:
                logger.info("Loaded LinkedIn cookies from %s", browser_method.__name__)
                return cj  # If we found both li_at and JSESSIONID, we're done
            else:
                logger.warning("Could not find li_at or JSESSIONID in %s", browser_method.__name__)
        except Exception as e:
            logger.warning("Failed to load cookies from %s: %s", browser_method.__name__, e)

    logger.info("Falling back to environment variables for LinkedIn cookies...")

    # If we reach here, none of the browsers worked, so use fallback
    # Expect the secrets to be set in the .env file
    li_at = LINKEDIN_LI_AT
    jsession = LINKEDIN_JSESSIONID

    # If these are still None or empty, then we can't proceed
    if not li_at or not jsession:
        logger.error("Could not load cookies from browsers or environment variables")
        sys.exit(1)

    # Build a RequestsCookieJar from env
    cookie_jar = RequestsCookieJar()
    cookie_jar.set("li_at", li_at, domain=".linkedin.com", path="/")
    cookie_jar.set("JSESSIONID", jsession, domain=".linkedin.com", path="/")

    logger.info("Loaded cookies from environment variables (li_at, JSESSIONID)")
    return cookie_jar

def get_linkedin_client(user_email, user_password):
    """
    1) Tries to log in to LinkedIn with username/password (using linkedin_api).
       - If that works, we return the authorized Linkedin client.
       - If there's a ChallengeException or any other error, we fallback to cookies.
    2) If we do fallback, we attempt to load cookies from the local browsers or .env file
       by calling load_linkedin_cookies().
    """
    if _INSTANCIATED.get("client"): 
        return _INSTANCIATED.get("client")
    try:
        # Attempt a fresh login with username/password
        logger.info("Attempting direct username/password login to LinkedIn...")
        linkedin_client = Linkedin(
            user_email,
            user_password,
            refresh_cookies=True  # force re-login
        )
        logger.info("Login successful with username/password")
        _INSTANCIATED["client"] = linkedin_client
        return linkedin_client

    except Exception as e:
        # Typically, you might catch ChallengeException or other specific errors here.
        # For simplicity, we catch all and fallback to cookies.
        logger.warning("Could not login with username/password (Challenge, 2FA, or other error). Falling back to cookies")
        logger.warning("Error detail: %s", e)

        # Fallback: load cookies from browser or .env
        cookie_jar = load_linkedin_cookies()
        linkedin_client = Linkedin(
            username="",  # not needed if we have valid cookies
            password="",
            cookies=cookie_jar
        )
        _INSTANCIATED["client"] = linkedin_client
        return linkedin_client

if __name__ == "__main__":
    # Initialize LinkedIn client
    linkedin_client = get_linkedin_client(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)

    profile = linkedin_client.get_profile(
            public_id="maxime-fournes-6b83b845",
        )

    print(profile)