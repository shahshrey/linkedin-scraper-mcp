import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from server import LinkedInLoginServer
import pytest_asyncio
import os

@pytest_asyncio.fixture
async def server():
    """Fixture to create a server instance with mocked playwright."""
    server = LinkedInLoginServer()
    
    # Mock playwright and browser components
    server.playwright = AsyncMock()
    server.browser = AsyncMock()
    server.context = AsyncMock()
    server.page = AsyncMock()
    server.login_page = AsyncMock()
    
    try:
        yield server
    finally:
        # Cleanup
        await server.cleanup()

@pytest.mark.asyncio
async def test_initialization():
    """Test server initialization."""
    server = LinkedInLoginServer()
    assert server is not None
    assert server.playwright is None
    assert server.browser is None
    assert server.context is None
    assert server.page is None
    assert server.login_page is None

@pytest.mark.asyncio
async def test_handle_initialize():
    """Test initialize handler."""
    server = LinkedInLoginServer()
    result = server.handle_initialize({})
    
    assert result["serverInfo"]["name"] == "linkedin-login-server"
    assert result["capabilities"]["tools"]["available"] is True
    assert result["capabilities"]["resources"]["available"] is False

@pytest.mark.asyncio
async def test_list_tools(server):
    """Test tools listing."""
    result = await server.handle_list_tools({})
    tools = result["tools"]
    
    assert len(tools) == 2
    assert tools[0]["name"] == "login"
    assert tools[1]["name"] == "check_login_status"
    
    # Verify login tool requires email and password
    login_tool = tools[0]
    assert "required" in login_tool["inputSchema"]
    assert "email" in login_tool["inputSchema"]["required"]
    assert "password" in login_tool["inputSchema"]["required"]

@pytest.mark.asyncio
async def test_successful_login(server):
    """Test successful login handling."""
    # Mock successful login
    server.login_page.login = AsyncMock(return_value=True)
    
    result = await server.handle_login({
        "email": "test@example.com",
        "password": "password123"
    })
    
    assert json.loads(result["content"][0]["text"])["success"] is True

@pytest.mark.asyncio
async def test_failed_login(server):
    """Test failed login handling."""
    # Mock failed login
    server.login_page.login = AsyncMock(side_effect=Exception("Login failed"))
    
    result = await server.handle_login({
        "email": "test@example.com",
        "password": "wrong_password"
    })
    
    response = json.loads(result["content"][0]["text"])
    assert response["success"] is False
    assert "Login failed" in response["error"]

@pytest.mark.asyncio
async def test_check_login_status_logged_in(server):
    """Test login status check when logged in."""
    server.login_page.is_logged_in = AsyncMock(return_value=True)
    
    result = await server.handle_check_login_status()
    assert json.loads(result["content"][0]["text"])["logged_in"] is True

@pytest.mark.asyncio
async def test_check_login_status_not_logged_in(server):
    """Test login status check when not logged in."""
    server.login_page.is_logged_in = AsyncMock(return_value=False)
    
    result = await server.handle_check_login_status()
    assert json.loads(result["content"][0]["text"])["logged_in"] is False

@pytest.mark.asyncio
async def test_handle_message_valid_request(server):
    """Test handling of valid JSON-RPC request."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    with patch('builtins.print') as mock_print:
        await server.handle_message(json.dumps(request))
        
    # Verify print was called with valid JSON response
    call_args = mock_print.call_args[0][0]
    response = json.loads(call_args)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "tools" in response["result"]

@pytest.mark.asyncio
async def test_handle_message_invalid_method(server):
    """Test handling of invalid method request."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "invalid_method",
        "params": {}
    }
    
    with patch('builtins.print') as mock_print:
        await server.handle_message(json.dumps(request))
        
    # Verify error response
    call_args = mock_print.call_args[0][0]
    response = json.loads(call_args)
    assert response["error"]["code"] == -32601
    assert "Unknown method" in response["error"]["message"]

@pytest.mark.asyncio
async def test_cleanup(server):
    """Test cleanup of browser resources."""
    await server.cleanup()
    
    assert server.context.close.called
    assert server.browser.close.called
    assert server.playwright.stop.called

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_linkedin_login():
    """Integration test for actual LinkedIn login."""
    server = LinkedInLoginServer()
    try:
        # Initialize real browser components
        await server.initialize_browser()
        
        # Test with actual credentials from environment variables
        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")
        
        if not email or not password:
            pytest.skip("LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables must be set")
        
        # Attempt actual login
        result = await server.handle_login({
            "email": email,
            "password": password
        })
        
        # Verify login success
        response = json.loads(result["content"][0]["text"])
        assert response["success"] is True
        
        # Verify logged in status
        status_result = await server.handle_check_login_status()
        status_response = json.loads(status_result["content"][0]["text"])
        assert status_response["logged_in"] is True
        
    finally:
        await server.cleanup()
