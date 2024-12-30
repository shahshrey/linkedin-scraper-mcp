#!/usr/bin/env python3
import asyncio
import json
import sys
import logging
from typing import Dict, Any
from playwright.async_api import async_playwright
from login_page import LoginPage
from mcp.types import ErrorData as McpError, METHOD_NOT_FOUND

# Constants
PROTOCOL_VERSION = "0.1.0"
SERVER_NAME = "linkedin-login-server"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

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
                    "name": "login",
                    "description": "Log in to LinkedIn using provided credentials",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "string",
                                "description": "LinkedIn email/username"
                            },
                            "password": {
                                "type": "string",
                                "description": "LinkedIn password"
                            }
                        },
                        "required": ["email", "password"]
                    }
                },
                {
                    "name": "check_login_status",
                    "description": "Check if currently logged in to LinkedIn",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
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

        if tool_name == "login":
            return await self._handle_login(arguments)
        elif tool_name == "check_login_status":
            return await self._handle_check_login_status()
        else:
            raise McpError(
                METHOD_NOT_FOUND,
                f"Unknown tool: {tool_name}"
            )

    async def _handle_login(self, arguments: Dict) -> Dict:
        """Handle LinkedIn login requests."""
        try:
            await self._ensure_browser()
            email = arguments.get("email")
            password = arguments.get("password")
            
            success = await self.login_page.login(email, password)
            
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "success": success,
                        "message": "Successfully logged in to LinkedIn"
                    })
                }]
            }
        except Exception as e:
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

    async def _handle_check_login_status(self) -> Dict:
        """Handle login status check requests."""
        try:
            await self._ensure_browser()
            is_logged_in = await self.login_page.is_logged_in()
            
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "logged_in": is_logged_in
                    })
                }]
            }
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Failed to check login status: {str(e)}"
                    })
                }],
                "isError": True
            }

    async def _cleanup(self):
        """Clean up browser context, browser, and Playwright instance."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

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
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)

        logger.info(f"Starting {SERVER_NAME}")
        
        for line in sys.stdin:
            await self._handle_message(line.strip())

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

if __name__ == "__main__":
    server = LinkedInLoginServer()
    asyncio.run(server.run())
