#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
from typing import Dict, Any, List
from playwright.async_api import async_playwright
from login_page import LoginPage
from mcp.types import ErrorData as McpError, METHOD_NOT_FOUND
from profile_page import ProfilePage
from dotenv import load_dotenv
from pydantic import BaseModel, Field
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
PROTOCOL_VERSION = "0.1.0"
SERVER_NAME = "linkedin-scraper"


try:
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        raise ValueError("Required environment variables LINKEDIN_EMAIL and LINKEDIN_PASSWORD are not set")
except Exception as e:
    logger.error(f"Environment configuration error: {str(e)}")
    sys.exit(1)


class ScrapePostsInput(BaseModel):
    profile_ids: List[str] = Field(
        description="List of LinkedIn profile IDs to scrape"
    )
    max_posts: int = Field(
        default=5,
        description="Maximum number of posts to scrape per profile"
    )

class Tool(BaseModel):
    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    inputSchema: dict = Field(description="JSON schema for the tool's input")

class ScraperTool(Tool):
    name: str = Field(default="scrape_posts")
    description: str = Field(default="Scrape LinkedIn posts from specified profiles (handles login automatically)")
    inputSchema: dict = Field(default_factory=lambda: ScrapePostsInput.model_json_schema())

class ToolsList(BaseModel):
    tools: List[Tool]

# Add new input model for connection requests
class SendConnectionInput(BaseModel):
    search_query: str = Field(
        description="Search query to find LinkedIn profiles (e.g., 'Software Engineer at Google')"
    )
    max_connections: int = Field(
        default=10,
        description="Maximum number of connection requests to send"
    )
    custom_note: str = Field(
        default="",
        description="Optional custom note to include with connection requests"
    )

# Add new connection tool
class ConnectionTool(Tool):
    name: str = Field(default="send_connections")
    description: str = Field(default="Search for LinkedIn profiles and send connection requests")
    inputSchema: dict = Field(default_factory=lambda: SendConnectionInput.model_json_schema())

class LinkedInLoginServer:
    def __init__(self) -> None:
        """Initialize the server and define RPC method handlers."""
        self._handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_list_tools,
            "tools/call": self._handle_call_tool,
            "resources/list": self._handle_list_resources,
            "resources/templates/list": self._handle_list_resource_templates,
            "notifications/initialized": self._handle_notification,
            "cancelled": self._handle_cancelled,
        }
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.login_page = None
        self.profile_page = None
        self.search_page = None

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        client_protocol_version = params.get('protocolVersion', PROTOCOL_VERSION)
        return {
            'protocolVersion': client_protocol_version,
            'serverInfo': {
                'name': SERVER_NAME,
                'version': PROTOCOL_VERSION
            },
            'capabilities': {
                'tools': {
                    'available': True
                },
                'resources': {
                    'available': False
                },
                'resourceTemplates': {
                    'available': False
                }
            }
        }

    async def _handle_list_tools(self, _: Any) -> Dict:
        """Handle listing available tools."""
        tools_list = ToolsList(
            tools=[
                ScraperTool(),
                ConnectionTool()  # Add the new tool
            ]
        )
        return tools_list.model_dump()

    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        # Close any existing sessions
        await self._cleanup()
        
        try:
            # Use the same configuration as our working direct test
            logger.info("Starting Playwright")
            self.playwright = await async_playwright().start()
            
            logger.info("Launching browser")
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                slow_mo=100
            )
            
            logger.info("Creating browser context")
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
            
            logger.info("Creating new page")
            self.page = await self.context.new_page()
            
            logger.info("Initializing LoginPage")
            self.login_page = LoginPage(self.page)
            
            self.profile_page = ProfilePage(self.page)
            
            logger.info("Browser session initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {str(e)}")
            await self._cleanup()
            raise Exception(f"Browser initialization failed: {str(e)}")

    async def _handle_call_tool(self, params: Any) -> Dict:
        """Handle tool execution requests."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "scrape_posts":
            return await self._handle_scrape_posts(arguments)
        elif tool_name == "send_connections":
            return await self._handle_send_connections(arguments)
        else:
            raise McpError(
                METHOD_NOT_FOUND,
                f"Unknown tool: {tool_name}"
            )

    async def _handle_scrape_posts(self, arguments: Dict) -> Dict:
        """Handle LinkedIn post scraping requests with integrated login."""
        try:
            # Validate input
            input_data = ScrapePostsInput(**arguments)
            
            # Use validated data
            profile_ids = input_data.profile_ids
            max_posts = input_data.max_posts
            
            # Initialize browser if needed
            if not self.page or not self.context or not self.browser:
                await self._ensure_browser()
            

            
            # Only login if not already logged in
            if not await self.login_page.is_logged_in():
                login_success = await self.login_page.login(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
                if not login_success:
                    raise Exception("Failed to log in to LinkedIn")
            
            # Proceed with scraping
            posts = await self.profile_page.scrape_linkedin_posts(profile_ids, max_posts)

            # Return results before cleanup
            result = {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "posts": posts
                    })
                }]
            }

            # Only cleanup if we're done with all operations
            await self._cleanup()
            return result

        except Exception as e:
            logger.error(f"Failed to scrape posts: {str(e)}")
            await self._cleanup()  # Ensure cleanup on error
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": False,
                        "error": str(e)
                    })
                }],
                "isError": True
            }

    async def _handle_send_connections(self, arguments: Dict) -> Dict:
        """Handle LinkedIn connection request sending."""
        try:
            # Validate input
            input_data = SendConnectionInput(**arguments)
            logger.debug(f"Validated input data: {input_data}")

            # Initialize browser if needed
            if not self.page or not self.context or not self.browser:
                logger.info("Browser not initialized, initializing now.")
                await self._ensure_browser()
            
            # Login if necessary
            if not await self.login_page.is_logged_in():
                logger.info("Not logged in, attempting login.")
                login_success = await self.login_page.login(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
                if not login_success:
                    raise Exception("Failed to log in to LinkedIn")
                logger.info("Login successful.")

            # Search for profiles
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={input_data.search_query}"
            logger.debug(f"Navigating to search URL: {search_url}")
            await self.page.goto(search_url)
            await self.page.wait_for_timeout(2000)
            logger.info("Search page loaded.")

            sent_requests = 0
            results = []
            
            for _ in range(min(input_data.max_connections, 3)):
                connect_buttons = await self.page.query_selector_all("button:has-text('Connect')")
                logger.debug(f"Found {len(connect_buttons)} connect buttons on the page.")

                for button in connect_buttons:
                    if sent_requests >= input_data.max_connections:
                        logger.info("Reached maximum connection requests limit.")
                        break
                        
                    try:
                        # Updated selector to find the profile name using the correct class structure
                        profile_card = await button.evaluate("""
                            button => {
                                const container = button.closest('.entity-result__item');
                                if (!container) return null;
                                const nameElement = container.querySelector('.entity-result__title-text a');
                                const titleElement = container.querySelector('.entity-result__primary-subtitle');
                                return {
                                    name: nameElement ? nameElement.innerText.trim() : 'Unknown Profile',
                                    title: titleElement ? titleElement.innerText.trim() : ''
                                };
                            }
                        """)
                        
                        if not profile_card or not profile_card.get('name'):
                            logger.warning("Profile information not found, trying alternative selector...")
                            # Alternative selector for the new LinkedIn UI
                            profile_card = await button.evaluate("""
                                button => {
                                    const container = button.closest('.iLNPXRzIPSRzJxVVZISWYouxrvwqQ');
                                    if (!container) return null;
                                    const nameElement = container.querySelector('.vjvKoXFFJtfnpBNnkgFTzWnDmsSASvTcGEESnk a');
                                    const titleElement = container.querySelector('.hnypMlQNtRKZTJxKVVHfxzWpjYbYocHvxY');
                                    return {
                                        name: nameElement ? nameElement.innerText.trim() : 'Unknown Profile',
                                        title: titleElement ? titleElement.innerText.trim() : ''
                                    };
                                }
                            """)

                        if not profile_card or not profile_card.get('name'):
                            logger.warning("Profile card not found, skipping this button.")
                            continue

                        logger.info(f"Attempting to connect with profile: {profile_card['name']} ({profile_card['title']})")

                        # Rest of the connection logic remains the same
                        await button.click()
                        await self.page.wait_for_timeout(1000)
                        
                        if input_data.custom_note:
                            logger.debug("Adding custom note to connection request.")
                            add_note_button = await self.page.wait_for_selector("button:has-text('Add a note')", timeout=2000)
                            if add_note_button:
                                await add_note_button.click()
                                await self.page.wait_for_timeout(500)
                                await self.page.fill("textarea[name='message']", input_data.custom_note)
                                send_button = await self.page.wait_for_selector("button:has-text('Send')", timeout=2000)
                                if send_button:
                                    await send_button.click()
                        else:
                            send_button = await self.page.wait_for_selector("button:has-text('Send')", timeout=2000)
                            if send_button:
                                await send_button.click()
                        
                        results.append({
                            "name": profile_card['name'],
                            "title": profile_card['title'],
                            "status": "success"
                        })
                        sent_requests += 1
                        logger.info(f"Connection request sent to {profile_card['name']} ({profile_card['title']}). Total sent: {sent_requests}")
                        await self.page.wait_for_timeout(1000)
                        
                    except Exception as e:
                        logger.error(f"Failed to send connection request to {profile_card['name']} ({profile_card['title']}): {str(e)}", exc_info=True)
                        continue
                
                if sent_requests >= input_data.max_connections:
                    break
                    
                next_button = await self.page.query_selector("button[aria-label='Next']")
                if next_button:
                    logger.info("Navigating to the next page of search results.")
                    await next_button.click()
                    await self.page.wait_for_timeout(1000)
                else:
                    logger.info("No more pages to navigate.")
                    break

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": True,
                        "connections_sent": sent_requests,
                        "results": results
                    })
                }]
            }

        except Exception as e:
            logger.error(f"Failed to send connection requests: {str(e)}", exc_info=True)
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": False,
                        "error": str(e)
                    })
                }],
                "isError": True
            }
        finally:
            logger.info("Cleaning up browser session.")
            await self._cleanup()

    async def _cleanup(self):
        """Clean up browser context, browser, and Playwright instance."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        finally:
            # Reset all browser-related instances after cleanup
            self.playwright = None
            self.browser = None
            self.context = None
            self.page = None
            self.login_page = None
            self.profile_page = None

    async def _handle_message(self, message: str) -> None:
        """Handle a single JSON-RPC message."""
        try:
            logger.debug(f"Received message: {message}")
            request = json.loads(message)
            method = request.get("method")
            params = request.get("params", {})

            logger.debug(f"Processing method: {method}")

            if method not in self._handlers:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Unknown method: {method}",
                    },
                }
            else:
                handler = self._handlers[method]
                # Check if handler is async or sync
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(params)
                else:
                    result = handler(params)

                if result is None:
                    return

                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": result
                }
                logger.debug(f"Request: {request}")
                logger.debug(f"Result: {result}")

            logger.debug(f"Sending response: {response}")
            print(json.dumps(response), flush=True)

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if "request" in locals() else None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)

    async def run(self) -> None:
        """Modified run method with proper exit handling"""
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)

        logger.info(f"Starting {SERVER_NAME}")
        
        try:
            while True:
                line = sys.stdin.readline()
                if not line:
                    logger.info("Received EOF, shutting down server")
                    break
                
                await self._handle_message(line.strip())
        finally:
            await self._cleanup()  # Only cleanup when server stops completely

    def _handle_list_resources(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the 'resources/list' RPC method.
        
        :param params: JSON parameters from the client.
        :return: An empty list of resources.
        """
        return {'resources': []}

    def _handle_list_resource_templates(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the 'resources/templates/list' RPC method.
        
        :param params: JSON parameters from the client.
        :return: An empty list of resource templates.
        """
        return {'resourceTemplates': []}

    def _handle_notification(self, params: Dict[str, Any]) -> None:
        """
        Handle notification methods that do not require a response.
        
        :param params: JSON parameters from the client.
        :return: None
        """
        logger.debug(f"Received notification with params: {params}")
        return None

    def _handle_cancelled(self, params: Dict[str, Any]) -> None:
        """
        Handle cancellation notifications.
        
        :param params: JSON parameters from the client.
        :return: None
        """
        logger.debug(f"Received cancellation with params: {params}")
        return None

    async def initialize_browser(self):
        """Initialize browser components for LinkedIn automation."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Set to True in production
                slow_mo=50  # Slows down operations to make them visible
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            self.login_page = LoginPage(self.page)
            return True
        except Exception as e:
            print(f"Failed to initialize browser: {str(e)}")
            await self._cleanup()
            raise

    async def _process_profiles(self):
        """Process profiles from the search page."""
        try:
            # Try to find profile cards on the page
            profile_cards = await self.page.query_selector_all(".iLNPXRzIPSRzJxVVZISWYouxrvwqQ")
            
            if not profile_cards:
                logger.error("No profile cards found on page")
                return
            
            for profile_card in profile_cards:
                try:
                    # Click the connect button within the profile card
                    connect_button = await profile_card.query_selector('button[aria-label^="Connect"]')
                    if connect_button:
                        await connect_button.click()
                        logger.info("Clicked connect button")

                        # Wait for the modal to appear
                        await self.page.wait_for_selector('.artdeco-modal', timeout=5000)
                        logger.info("Modal appeared")

                        # Click the "Send without a note" button
                        send_button = await self.page.query_selector('button[aria-label="Send without a note"]')
                        if send_button:
                            await send_button.click()
                            logger.info("Sent connection request without a note")
                        else:
                            logger.error("Send button not found")
                    else:
                        logger.info("Connect button not found for this profile")
                except Exception as e:
                    logger.error(f"Error processing profile card: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error processing profiles: {str(e)}", exc_info=True)

if __name__ == "__main__":
    server = LinkedInLoginServer()
    asyncio.run(server.run())
