import requests
import time
import sys
import os  # NEW: Import os to read environment variables
from pathlib import Path
import undetected_chromedriver as uc
import browser_cookie3
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Add project root to path for testing
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.core.interfaces import ContentFetcherStrategy
from src.core.config_loader import config


"""
class SimpleRequestsFetcher(ContentFetcherStrategy):
    def fetch(self, url: str) -> str:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            response = requests.get(url, timeout=15, headers=headers, stream=True)
            response.raise_for_status()
            return response.text[:100000]
        except Exception as e:
            if config.get('settings.verbose'):
                print(f"    [SimpleFetcher] Failed: {e}")
            return None
"""

class SimpleRequestsFetcher(ContentFetcherStrategy):
    """
    Fast, lightweight fetcher for standard static sites.
    """
    def fetch(self, url: str) -> dict:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            response = requests.get(url, timeout=15, headers=headers, stream=True)
            content = response.text[:100000]

            # .. note:: We could just return response.reason
            # Check for HTTP errors (4xx/5xx)
            if 400 <= response.status_code < 600:
                if response.status_code == 404:
                    status = 'broken'
                elif response.status_code == 403:
                    status = 'access_denied'
                else:
                    status = 'http_error'

                return {'status': status, 'content': content}
            return {'status': 'alive', 'content': content}

        except requests.exceptions.Timeout:
            if config.get('settings.verbose'):
                print(f"    [SimpleFetcher] Timeout: {url}")
            return {'status': 'timeout', 'content': None}
        except requests.exceptions.ConnectionError:
            if config.get('settings.verbose'):
                print(f"    [SimpleFetcher] Connection Error: {url}")
            return {'status': 'invalid_entry', 'content': None}
        except Exception as e:
            if config.get('settings.verbose'):
                print(f"    [SimpleFetcher] Failed: {e}")
            return {'status': 'general_error', 'content': None}



class BaseSeleniumFetcher(ContentFetcherStrategy):
    """
    Base class for cookie-dependent fetching using Selenium.
    Handles driver setup, cookie retrieval, and basic navigation logic.
    """
    def __init__(self, strategy_key):
        self.strategy_key = strategy_key
        self.domain = config.get(f'strategies.{strategy_key}.cookie_domain')
        self.cookie_name = config.get(f'strategies.{strategy_key}.cookie_name')
        self.cookie = self._get_cookie()
        self.options = uc.ChromeOptions()
        #if config.get(f'strategies.{strategy_key}.headless', False):
        #    # In a real setup, this would add a headless argument to options
        #    pass

    def _get_chrome_options(self):
        """Creates and configures a fresh ChromeOptions object."""
        options = uc.ChromeOptions()
        if config.get(f'strategies.{self.strategy_key}.headless', False):
            options.add_argument('--headless=new')
        return options

    def _get_cookie(self):
        """
        Tries to auto-discover session cookie from local browsers OR
        retrieves it from an environment variable (e.g., LINKEDIN_COOKIE).
        """
        # 1. Check Environment Variable (Manual Override - Highest Priority)
        env_var_name = f"{self.strategy_key.upper()}_COOKIE"
        manual_cookie = os.getenv(env_var_name)
        if manual_cookie:
            print(f"    [{self.strategy_key.title()}Fetcher] ✅ Using manual cookie from ${env_var_name}.")
            return manual_cookie

        # 2. Try Local Browser Discovery
        try:
            # Try Chrome
            cookies = browser_cookie3.chrome(domain_name=self.domain)
            for c in cookies:
                if c.name == self.cookie_name: return c.value
        except Exception:
            pass

        try:
            # Try Firefox
            cookies = browser_cookie3.firefox(domain_name=self.domain)
            for c in cookies:
                if c.name == self.cookie_name: return c.value
        except Exception:
            pass

        print(f"    [{self.strategy_key.title()}Fetcher] ⚠️ No cookie found in local browser or .env.")
        return None

    def fetch(self, url: str) -> dict:
        if not self.cookie:
            print(f"    [{self.strategy_key.title()}Fetcher] ⚠️ No '{self.cookie_name}' cookie found. Skipping.")
            return {'status': 'skip_no_cookie', 'content': None}

        driver = None
        try:
            if config.get('settings.verbose'):
                print(f"    [{self.strategy_key.title()}Fetcher] Booting driver for {url[:30]}...")

            # Get options
            options = self._get_chrome_options()

            # Create drivers
            driver = uc.Chrome(options=options,
                               use_subprocess=True,
                               version_main=142)
            # 1. Set Cookie
            if self.cookie:
                driver.get(f"https://www{self.domain}")
                driver.add_cookie({
                    'name': self.cookie_name,
                    'value': self.cookie,
                    'domain': self.domain
                })

            # 2. Navigate to Article
            #print(f"Navigating to: {url}")
            driver.get(url)

            # --- PHASE 1: Wait for Structure (Smart Wait) ---
            # This ensures the browser hasn't crashed and the URL is valid.
            # It waits up to 15 seconds for the <body> tag to appear.
            #print("Waiting for page structure...")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # --- PHASE 2: Let JS Settle (Hydration Wait) ---
            # Even after <body> loads, LinkedIn text fades in via JS.
            # We force a pause to ensure the text is readable in the HTML.
            #print("Waiting for content hydration (JS settling)...")
            time.sleep(10)  # Allow JS to settle

            # --- DEBUG: Save HTML ---
            #print("Saving HTML snapshot...")
            #html_content = self.driver.page_source
            #with open("debug_page.html", "w", encoding="utf-8") as f:
            #    f.write(html_content)

            page_text = driver.find_element(By.TAG_NAME, "body").text

            # Add a basic check for post non-availability
            status_check = self._check_content_status(page_text)

            if status_check != 'alive':
                return {'status': status_check, 'content': page_text}

            return {'status': 'alive', 'content': page_text}

        except Exception as e:
            print(f"    [{self.strategy_key.title()}Fetcher] Error: {e}")
            return {'status': 'general_error', 'content': None}
        finally:
            if driver: driver.quit()

    def _check_content_status(self, content: str) -> str:
        """
        Analyzes the fetched text for common post-not-found or login wall indicators.
        """
        content_lower = content.lower()

        # Keywords for 'Post Not Found' or 'Unavailable' (The 'broken' state)
        broken_keywords = [
            "post not found",
            "page not available",
            "content isn't available",
            "this page is broken",
            "no longer available",
            "error 404",
            "sorry, this",
            "post cannot be displayed",  # LinkedIn specific
            "post is unavailable",
            "page you're looking for cannot be found"
        ]

        if any(kw in content_lower for kw in broken_keywords):
            return 'broken'

        # Keywords for a Login Wall (The 'login_wall' state)
        login_keywords = ["sign in", "login to continue", "log into facebook", "join linkedin"]
        if any(kw in content_lower for kw in login_keywords):
            return 'login_wall'

        # A successful page should have some content.
        if len(content) < 500:
            return 'low_content'

        return 'alive'

# Specialized Fetchers (inheriting from Base)
class LinkedInFetcher(BaseSeleniumFetcher):
    def __init__(self):
        super().__init__('linkedin')


class FacebookFetcher(BaseSeleniumFetcher):
    def __init__(self):
        super().__init__('facebook')


class ConsentBypassFetcher2(BaseSeleniumFetcher):
    """
    Specialized fetcher to handle the Google/Meta consent pages.
    It loads the page, finds the 'Accept all' form/button, submits it,
    and then retrieves the content from the redirected page.
    """

    def __init__(self):
        # 'consent_bypass' is the strategy key used in the config mock above
        super().__init__('consent_bypass')
        # A list of button texts (case-insensitive) most likely to grant access
        self.ACCEPT_BUTTON_TEXTS = [
            "Accept all", "Accept", "Agree", "Continue", "I Agree",
            "Allow all", "Got it", "OK", "Consent", "Confirm"
        ]

    def bypass_consent_page(self, url: str) -> str:
        driver = None
        try:
            if config.get('settings.verbose'):
                print(f"    [ConsentBypassFetcher] Booting driver for consent bypass: {url[:30]}...")

            # Get driver
            options = self._get_chrome_options()
            driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
            driver.get(url)
            time.sleep(5)

            print("    [ConsentBypassFetcher] Attempting to find and click a generic 'Accept' button...")

            if "consent.google.com" in driver.current_url:
                try:
                    # XPath to find the FORM that contains the 'Accept all' submit button.
                    # This targets the form with the specific input field that has value='Accept all'.
                    google_accept_form_xpath = "//form[./input[@type='submit' and @value='Accept all']]"

                    # Wait for the form element to be present
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, google_accept_form_xpath))
                    )
                    accept_form = driver.find_element(By.XPATH, google_accept_form_xpath)

                    # Explicitly submit the form, which is the most reliable way to complete the consent action.
                    accept_form.submit()

                    if config.get('settings.verbose'):
                        print(f"    [ConsentBypassFetcher] Successfully submitted Google-specific form.")
                    time.sleep(10)  # Wait for redirection to complete
                    return {'status': 'success', 'content': driver.find_element(By.TAG_NAME, "body").text}

                except Exception as e:
                    if config.get('settings.verbose'):
                        print(
                            f"    [ConsentBypassFetcher] Warning: Google-specific form submission failed, falling back to generic loop. Error: {e}")

            # --- STRATEGY 2: GENERIC LOOP FALLBACK (More robust than complex OR XPath) ---

            found_and_clicked = False

            for text in self.ACCEPT_BUTTON_TEXTS:
                # 1. Look for <button> by text (case-insensitive)
                button_xpath = f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"

                # 2. Look for <input type='submit'|'button'> by value (case-insensitive)
                input_xpath = f"//input[@type='submit' or @type='button'][contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"

                # Combine the current search paths
                generic_xpath = f"{button_xpath} | {input_xpath}"

                try:
                    # Find any matching element immediately
                    accept_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, generic_xpath))
                    )

                    # Use JavaScript to ensure the click works
                    driver.execute_script("arguments[0].click();", accept_button)

                    if config.get('settings.verbose'):
                        print(f"    [ConsentBypassFetcher] Successfully clicked generic button ({text}) via JS.")
                    found_and_clicked = True
                    break

                except (TimeoutException, NoSuchElementException):
                    # Continue to the next button text if this one wasn't found/clickable
                    continue
                except Exception as e:
                    if config.get('settings.verbose'):
                        print(f"    [ConsentBypassFetcher] Error during generic click attempt for '{text}': {e}")
                    # If an unexpected error occurs, stop the loop
                    break

            if found_and_clicked:
                time.sleep(10)  # Wait for redirection/content to load after click
                return {'status': 'success', 'content': driver.find_element(By.TAG_NAME, "body").text}
            else:
                if config.get('settings.verbose'):
                    print(f"    [ConsentBypassFetcher] Could not find or click an accept button via any method.")
                return {'status': 'consent_failure', 'content': None}

        except Exception as e:
            if config.get('settings.verbose'):
                print(f"    [ConsentBypassFetcher] Failed to bypass consent: {e}")
            return {'status': 'selenium_error', 'content': None}
        finally:
            if driver: driver.quit()


import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException


# Ensure these imports exist in your file:
# from src.core.interfaces import ContentFetcherStrategy
# from src.core.config_loader import config

class ConsentBypassFetcher(BaseSeleniumFetcher):
    """
    Specialized fetcher to handle Google/Meta/CMP consent pages.
    """

    def __init__(self):
        super().__init__('consent_bypass')

    def bypass_consent_page(self, url: str) -> dict:
        driver = None
        try:
            if config.get('settings.verbose'):
                print(f"    [ConsentBypassFetcher] Booting driver for: {url[:30]}...")

            options = self._get_chrome_options()
            driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
            driver.get(url)

            # Allow initial redirects/loading
            time.sleep(3)

            # --- ROUTING LOGIC ---
            current_url = driver.current_url.lower()

            if "consent.google.com" in current_url:
                result = self._handle_google_consent(driver)
            elif "consent.yahoo.com" in current_url:
                result = self._handle_yahoo_consent(driver)
            else:
                # Generic handles standard pages AND Iframes (Guardian, etc)
                result = self._handle_generic_consent(driver)

            if result:
                if config.get('settings.verbose'):
                    print("    [ConsentBypass] Click successful. Waiting for reload...")
                time.sleep(5)  # Wait for page reload/hydration
                return {'status': 'success', 'content': driver.find_element(By.TAG_NAME, "body").text}
            else:
                return {'status': 'consent_failure', 'content': None}

        except Exception as e:
            if config.get('settings.verbose'):
                print(f"    [ConsentBypassFetcher] Critical Error: {e}")
            return {'status': 'selenium_error', 'content': None}
        finally:
            if driver: driver.quit()

    def _handle_google_consent(self, driver) -> bool:
        if config.get('settings.verbose'): print("    [ConsentBypass] Detected Google Consent Wall.")
        buttons_to_try = ["Accept all", "I agree", "Agree", "Alles akzeptieren"]

        for text in buttons_to_try:
            xpath = f"//button[contains(., '{text}')] | //div[@role='button'][contains(., '{text}')]"
            try:
                buttons = WebDriverWait(driver, 2).until(EC.presence_of_all_elements_located((By.XPATH, xpath)))
                for btn in buttons:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].click();", btn)
                        return True
            except:
                continue
        return False

    def _handle_yahoo_consent(self, driver) -> bool:
        if config.get('settings.verbose'): print("    [ConsentBypass] Detected Yahoo/Oath Consent Wall.")
        try:
            btn = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@name='agree'] | //button[contains(., 'Accept all')]"))
            )
            btn.click()
            return True
        except:
            return False

    def _handle_generic_consent(self, driver) -> bool:
        """
        Handles generic buttons AND Iframe-based CMPs (Sourcepoint/Guardian).
        """
        if config.get('settings.verbose'): print("    [ConsentBypass] Attempting Generic/Iframe CMP Bypass.")

        # Keywords expanded for The Guardian ("Yes, I'm happy") and others
        keywords = [
            "Accept all", "Allow all", "I Agree", "Accept Cookies",
            "Yes, I’m happy", "Yes, I'm happy", "I'm happy",  # Guardian specific
            "Consent", "Got it", "Allow selection", "Agree"
        ]

        # --- STRATEGY A: Check for IFRAMES (The Guardian Fix) ---
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        for frame in frames:
            try:
                fid = frame.get_attribute("id")
                # Sourcepoint usually uses IDs starting with 'sp_message_iframe'
                if fid and "sp_message_iframe" in fid:
                    if config.get('settings.verbose'):
                        print(f"    [ConsentBypass] Found Sourcepoint Iframe ({fid}). Switching context.")

                    driver.switch_to.frame(frame)

                    # Search for buttons INSIDE the iframe
                    if self._click_button_by_text(driver, keywords):
                        driver.switch_to.default_content()  # Always switch back
                        return True

                    driver.switch_to.default_content()
            except (StaleElementReferenceException, NoSuchElementException):
                continue
            except Exception as e:
                print(f"Iframe error: {e}")
                driver.switch_to.default_content()

        # --- STRATEGY B: Check Main Document (Standard) ---
        return self._click_button_by_text(driver, keywords)

    def _click_button_by_text(self, context_driver, keywords):
        """Helper to find and click a button by text within a specific context (driver or frame)."""
        for text in keywords:
            # XPath Explanation:
            # 1. Matches <button> with text
            # 2. Matches <button> with title attribute (Guardian uses title="Yes, I’m happy")
            xpath = (
                f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')] | "
                f"//button[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")

            try:
                element = WebDriverWait(context_driver, 1).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                # Try JS Click first as it's more robust against overlays
                context_driver.execute_script("arguments[0].click();", element)
                if config.get('settings.verbose'):
                    print(f"    [ConsentBypass] Clicked '{text}' via JS.")
                return True
            except:
                continue
        return False


class FetchRouter:
    """
    The 'Agentic' component.
    Decides WHICH fetcher to use based on the URL or previous failures.
    """

    def __init__(self):
        self.simple = SimpleRequestsFetcher()
        self.fetchers = {}

        # Conditionally initialize heavyweight fetchers
        if config.get('strategies.linkedin.enabled'):
            self.fetchers['linkedin'] = LinkedInFetcher()

        if config.get('strategies.facebook.enabled'):
            self.fetchers['facebook'] = FacebookFetcher()

        # Initialize the new consent bypass fetcher
        if config.get('strategies.consent_bypass.enabled'):
            self.fetchers['consent_bypass'] = ConsentBypassFetcher()

    def get_content(self, url: str) -> dict:  # Updated to return dict
        # 1. Rule-Based Routing (Fast)
        if "linkedin.com" in url and 'linkedin' in self.fetchers:
            print(f"    [Router] 🔗 Routing to specialized LinkedInFetcher for {url[:30]}...")
            return self.fetchers['linkedin'].fetch(url)  # result is a dict

        if any(d in url for d in ['.facebook.com', 'meta.com', 'instagram.com']) and 'facebook' in self.fetchers:
            print(f"    [Router] 📘 Routing to specialized FacebookFetcher for {url[:30]}...")
            return self.fetchers['facebook'].fetch(url)  # result is a dict

        # 2. Try Simple Fetch
        result = self.simple.fetch(url)
        content = result['content']
        status = result['status']

        # 3. Intelligent Fallback: Consent Wall
        # Only check if we actually have content to check
        #if content and self._is_consent_wall(content) and 'consent_bypass' in self.fetchers:
        #    print("    [Router] 🍪 Generic Consent Wall suspected...")

        # 3. Intelligent Fallback: Check for Consent Wall
        #if status == 'alive' and self._is_consent_wall(content) and 'consent_bypass' in self.fetchers:
        if status == 'alive' and self._is_consent_wall(content) and 'consent_bypass' in self.fetchers:
            print("    [Router] 🍪 Consent Wall detected. Attempting Selenium bypass...")
            consent_fetcher = self.fetchers['consent_bypass']
            result = consent_fetcher.bypass_consent_page(url)
            status = result['status']

            if status == 'success':
                if config.get('settings.verbose'):
                    print("    [Router] ✅ Consent bypass successful. Content retrieved.")
            else:
                if config.get('settings.verbose'):
                    print(f"    [Router] ❌ Consent bypass failed. Status: {status}")

        # 4. Final Check: Login Wall (Only if content is still limited/bad and not already handled)
        # This checks for a login wall that the SimpleFetcher might have hit,
        # and which wasn't solved by the consent bypass (e.g., SimpleFetcher failed due to 401/403)
        #elif status != 'success' and self._is_login_wall(content):
        elif status == 'alive' and self._is_login_wall(content):
            if config.get('settings.verbose'):
                print("    [Router] 🧱 Login Wall detected by SimpleFetcher. Returning failed status.")
            status = 'login_wall'  # Ensure the status is explicitly login_wall if the content confirms it.

        # 4. Intelligent Fallback for Login Wall on generic sites
        # NOTE: This only runs if SimpleFetcher returned 'alive' but contained login keywords.
        #if status == 'alive' and self._is_login_wall(content):
        #    print("    [Router] 🧱 Login Wall detected by SimpleFetcher. Status updated.")
        #    result['status'] = 'login_wall_simple'


        return result

    """
    def get_content(self, url: str) -> str:
        # 1. Rule-Based Routing (Fast)
        if "linkedin.com" in url and 'linkedin' in self.fetchers:
            print(f"    [Router] 🔗 Routing to specialized LinkedInFetcher for {url[:30]}...")
            return self.fetchers['linkedin'].fetch(url)

        if any(d in url for d in ['.facebook.com', 'meta.com', 'instagram.com']) and 'facebook' in self.fetchers:
            print(f"    [Router] 📘 Routing to specialized FacebookFetcher for {url[:30]}...")
            return self.fetchers['facebook'].fetch(url)

        # 2. Try Simple Fetch
        content = self.simple.fetch(url)

        # 3. Intelligent Fallback: Check for Consent Wall
        if self._is_consent_wall(content) and 'consent_bypass' in self.fetchers:
            print("    [Router] 🍪 Generic Consent Wall suspected by SimpleFetcher. Attempting Selenium bypass...")
            consent_fetcher = self.fetchers['consent_bypass']
            # Re-fetch the content using the bypass logic
            content = consent_fetcher.bypass_consent_page(url)

            if content:
                print("    [Router] ✅ Consent bypass successful. Content retrieved.")
            else:
                print("    [Router] ❌ Consent bypass failed. Returning limited or no content.")

        # 3. Intelligent Fallback (The Agentic check)
        if self._is_login_wall(content):
            print("    [Router] 🧱 Login Wall detected by SimpleFetcher. No specialized fallbacks configured yet.")
            # Future: Here, you could have a generic headless browser fallback.

        return content
    """


    def _is_login_wall(self, content):
        # Return False if no content. Let the status code handle errors.
        if not content: return False
        keywords = ["Sign In", "Login to continue", "Verify you are human"]
        if len(content) < 2000 and any(k in content for k in keywords):
            if not self._is_consent_wall(content):
                return True
        return False

    def _is_consent_wall(self, content):
        """
        Checks if the retrieved HTML content is a generic Cookie/Consent request.
        Uses common linguistic patterns and content length.
        """
        if not content: return False

        # Keywords highly indicative of a consent or cookie notice
        consent_keywords = [
            "cookie", "cookies", "consent", "data protection",
            "privacy setting", "manage preferences", "we use", "our use of",
            "before you continue", "accept all"
        ]

        # Check if a combination of keywords is present
        keyword_count = sum(1 for keyword in consent_keywords if keyword in content.lower())

        # We consider it a consent wall if at least 3 distinct keywords are present
        # AND the content length suggests it's a full page or a large modal (not just a tiny banner).
        is_generic_consent = (keyword_count >= 3) and (len(content) > 1000)

        # Optionally, check for the specific Google consent if that URL is in the response
        is_google_consent = "consent.google.com" in content

        return is_generic_consent or is_google_consent


# --- TEST BLOCK ---
if __name__ == "__main__":

    # Libraries
    import json


    # -----------------------------------------------------------------
    # Configuration
    # -----------------------------------------------------------------
    # File with tests
    tests_file = Path('./src/fixtures') / 'tests_fetcher.json'
    # Create the Path object
    output_path = Path("outputs/tests/fetcher_html_outputs")
    # Create directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    # Show information
    print(f"📂 Output folder set to: {output_path.absolute()}")

    # Choose which categories to run
    # Groups of test to run
    # Options: ["ALL"] or [] to run everything.
    # Options: ["http_status_checks", "login_walls"] for specific.
    GROUPS_TO_RUN = [
        "http_status_checks",
        "consent_bypass_success",
        "google_ecosystem",
        "login_walls"
    ]

    GROUPS_TO_RUN = ["ALL"]
    GROUPS_TO_RUN = ['linkedin_specialized']
    # -----------------------------------------------------------------


    print("\n--- Testing FetchRouter with Specialized Fetchers ---")
    print("NOTE: Set environment variable like 'export LINKEDIN_COOKIE=\"...\"' for full specialized tests.")

    router = FetchRouter()

    try:
        with open(tests_file, "r") as f:
            full_suite = json.load(f)
    except FileNotFoundError:
        print("❌ {tests_file} not found.")
        sys.exit(1)

    # 3. Dynamic Group Selection Logic
    # Check if list is empty OR contains "ALL" (case-insensitive)
    if not GROUPS_TO_RUN or any(g.upper() == "ALL" for g in GROUPS_TO_RUN):
        print(f"📋 Configuration set to 'ALL'. Loading all {len(full_suite)} test categories...")
        GROUPS_TO_RUN = list(full_suite.keys())
    else:
        print(f"📋 Configuration set to specific groups: {GROUPS_TO_RUN}")

    # 4. Run the Tests
    total_passed = 0
    total_run = 0

    for group in GROUPS_TO_RUN:
        if group not in full_suite:
            print(f"\n⚠️  Warning: Group '{group}' not found in JSON. Skipping.")
            continue

        print(f"\n🔵 --- GROUP: {group.upper()} ---")
        test_cases = full_suite[group]

        for test in test_cases:
            if test.get("skip", False):
                print(f"   ⏩ [{test.get('id', '?')}] Skipping: {test['name']}")
                continue

            # --- DISPLAY ID HERE ---
            test_id = test.get('id', 'NA')
            print(f"\n 🔸 [{test_id}] Running: {test['name']}")
            print(f"    URL: {test['url'][:60]}...")

            # --- EXECUTE FETCH ---
            result = router.get_content(test['url'])
            status = result.get('status', 'unknown')
            content = result.get('content')
            content_len = len(content) if content else 0

            expected = test.get('expected_status', 'any')

            passed = (status == expected) or \
                     (expected == 'alive' and status == 'success') or \
                     (expected == 'success' and status == 'alive') or \
                     (expected == 'any')

            if passed:
                total_passed += 1
                icon = "✅"
            else:
                icon = "❌"
            total_run += 1

            print(f"    {icon} Result: {status.upper()} (Expected: {expected.upper()})")
            print(f"    📄 Content: {content_len} chars")

            # --- SAVE OUTPUT ---
            if test.get('save_output') and content:
                # Use ID in filename for easier sorting
                fname = test.get('file_name', f"{test_id}_{group}.html")
                file_path = output_path / fname

                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"    💾 Saved to {file_path}")
                except Exception as e:
                    print(f"    ⚠️ Failed to save file: {e}")

        # 5. Final Summary
    print("\n" + "=" * 30)
    print(f"🏁 TEST SUITE COMPLETED")
    print(f"📊 Summary: {total_passed}/{total_run} Passed")
    print("=" * 30)



    """
    Google	https://gemini.google.com/share/47410768bb31	Triggers consent.google.com (complex form/buttons).
    Google	https://www.youtube.com/	Often redirects to a full-page consent wall in Incognito/Headless.
    Yahoo/Oath	https://techcrunch.com/	Often redirects to consent.yahoo.com. Very strict wall.
    OneTrust	https://www.independent.co.uk/	Uses the "OneTrust" standard banner (generic handler should catch this).
    Generic	https://www.theguardian.com/	Has a banner at the bottom. Generic handler looking for "I'm happy" or "Yes, I agree".
    Strict Modal	https://www.businessinsider.com/	often uses a strict overlay that prevents scrolling.
    """
