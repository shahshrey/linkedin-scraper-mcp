import logging
from playwright.async_api import Page, TimeoutError
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoginPage:
    """Handles LinkedIn login page interactions."""
    
    def __init__(self, page: Page):
        self.page = page
        # Use simpler, more reliable selectors
        self.email_input = page.locator('input[id="username"]')
        self.password_input = page.locator('input[id="password"]')
        self.login_button = page.locator('button[type="submit"]')

    async def login(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Handle LinkedIn login with proper error handling and logging."""
        if not email or not password:
            raise ValueError("Email and password must be provided")

        try:
            # First check if already logged in
            if await self.is_logged_in():
                logger.info("Already logged in, skipping login process")
                return True

            logger.info("Attempting LinkedIn login")
            await self.page.goto("https://www.linkedin.com/login", timeout=60000)
            
            await self.email_input.fill(email)
            await self.password_input.fill(password)
            await self.login_button.click()

            # Wait for navigation and check for success
            try:
                # Wait for either feed page or security checkpoint
                await self.page.wait_for_url(
                    lambda url: any(x in url for x in ["feed", "checkpoint", "security-verification"]),
                    timeout=30000
                )
            except TimeoutError:
                raise Exception("Login failed: Timeout waiting for redirect")

            current_url = self.page.url

            # Check URL for success/failure
            if "feed" in current_url:
                logger.info("Successfully logged in")
                return True
            elif "checkpoint" in current_url or "security-verification" in current_url:
                logger.warning("Security verification required")
                return False
            else:
                raise Exception(f"Unexpected redirect URL: {current_url}")
            
        except Exception as e:
            logger.error(f"Login failed with error: {str(e)}")
            raise

    async def is_logged_in(self) -> bool:
        """Check if user is currently logged in to LinkedIn."""
        try:
            current_url = self.page.url
            return "feed" in current_url or "mynetwork" in current_url
        except Exception as e:
            logger.error(f"Error checking login status: {str(e)}")
            return False
