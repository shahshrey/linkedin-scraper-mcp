#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
from typing import Dict, Any
from playwright.async_api import async_playwright
from login_page import LoginPage
from mcp.types import ErrorData as McpError, METHOD_NOT_FOUND
from profile_page import ProfilePage
from dotenv import load_dotenv
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
        return {
            "tools": [
                {
                    "name": "scrape_posts",
                    "description": "Scrape LinkedIn posts from specified profiles (handles login automatically)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "profile_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of LinkedIn profile IDs to scrape"
                            },
                            "max_posts": {
                                "type": "integer",
                                "description": "Maximum number of posts to scrape per profile",
                                "default": 5
                            },
                        },
                        "required": ["profile_ids"]
                    }
                }
            ]
        }

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
                headless=True,
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
        else:
            raise McpError(
                METHOD_NOT_FOUND,
                f"Unknown tool: {tool_name}"
            )

    async def _handle_scrape_posts(self, arguments: Dict) -> Dict:
        """Handle LinkedIn post scraping requests with integrated login."""
        try:
            # Initialize browser if needed
            if not self.page or not self.context or not self.browser:
                await self._ensure_browser()
            

            
            # Only login if not already logged in
            if not await self.login_page.is_logged_in():
                login_success = await self.login_page.login(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
                if not login_success:
                    raise Exception("Failed to log in to LinkedIn")
            
            # Proceed with scraping
            profile_ids = arguments.get("profile_ids")
            max_posts = arguments.get("max_posts", 5)
            
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
                headless=True,  # Set to True in production
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

if __name__ == "__main__":
    server = LinkedInLoginServer()
    asyncio.run(server.run())
