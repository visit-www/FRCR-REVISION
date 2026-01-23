"""
Browser Automation Service using Playwright

Provides a wrapper around Playwright for browser automation tasks.
"""

import os
import json
from typing import Optional, List, Dict, Any

try:
    from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_INSTALLED = True
except ImportError:
    PLAYWRIGHT_INSTALLED = False


class BrowserAutomationService:
    """
    Browser automation service using Playwright.
    
    Usage:
        with BrowserAutomationService() as browser:
            browser.navigate("https://example.com")
            browser.fill("input[name='username']", "user")
            browser.click("button[type='submit']")
            cookies = browser.get_cookies()
    """
    
    def __init__(self, headless: bool = True, browser_type: str = "chromium"):
        """
        Initialize the browser automation service.
        
        Args:
            headless: Run browser in headless mode (default: True)
            browser_type: Browser to use: "chromium", "firefox", or "webkit"
        """
        if not PLAYWRIGHT_INSTALLED:
            raise ImportError("Playwright not installed. Run: pip install playwright && playwright install chromium")
        
        self.headless = headless
        self.browser_type = browser_type
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    def __enter__(self):
        """Start the browser session."""
        self.playwright = sync_playwright().start()
        
        # Select browser type
        if self.browser_type == "firefox":
            browser_launcher = self.playwright.firefox
        elif self.browser_type == "webkit":
            browser_launcher = self.playwright.webkit
        else:
            browser_launcher = self.playwright.chromium
        
        # Launch browser with anti-detection options
        self.browser = browser_launcher.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        
        # Create context with realistic settings
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            java_script_enabled=True,
            accept_downloads=True,
        )
        
        # Create page
        self.page = self.context.new_page()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the browser session."""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def navigate(self, url: str, wait_until: str = "load", timeout: int = 30000) -> None:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            wait_until: Wait condition: "load", "domcontentloaded", "networkidle"
            timeout: Timeout in milliseconds
        """
        self.page.goto(url, wait_until=wait_until, timeout=timeout)
    
    def get_current_url(self) -> str:
        """Get the current page URL."""
        return self.page.url
    
    def fill(self, selector: str, value: str, timeout: int = 5000) -> None:
        """Fill an input field."""
        self.page.fill(selector, value, timeout=timeout)
    
    def click(self, selector: str, timeout: int = 5000) -> None:
        """Click an element."""
        self.page.click(selector, timeout=timeout)
    
    def get_cookies(self) -> List[Dict[str, Any]]:
        """Get all cookies from the current context."""
        return self.context.cookies()
    
    def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        """Set cookies in the current context."""
        self.context.add_cookies(cookies)
    
    def save_cookies_to_file(self, filepath: str) -> None:
        """Save cookies to a JSON file."""
        cookies = self.get_cookies()
        with open(filepath, 'w') as f:
            json.dump(cookies, f, indent=2)
    
    def load_cookies_from_file(self, filepath: str) -> bool:
        """Load cookies from a JSON file."""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    cookies = json.load(f)
                self.set_cookies(cookies)
                return True
        except Exception as e:
            print(f"Error loading cookies: {e}")
        return False
    
    def take_screenshot(self, filepath: str) -> None:
        """Take a screenshot of the current page."""
        self.page.screenshot(path=filepath)
    
    def wait_for_selector(self, selector: str, timeout: int = 30000, state: str = "visible") -> None:
        """Wait for an element to appear."""
        self.page.wait_for_selector(selector, timeout=timeout, state=state)
    
    def get_text(self, selector: str) -> str:
        """Get text content of an element."""
        return self.page.text_content(selector)
    
    def evaluate(self, expression: str) -> Any:
        """Evaluate JavaScript in the page context."""
        return self.page.evaluate(expression)
