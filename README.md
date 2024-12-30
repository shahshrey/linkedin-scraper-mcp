# LinkedIn Login MCP Server

An MCP (Model Context Protocol) server that provides LinkedIn login functionality using Playwright for browser automation.

## Features

- LinkedIn login with email/password
- Login status checking
- Proper error handling and logging
- Comprehensive test suite
- Configurable through environment variables

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install
```

## Configuration

The server can be configured through environment variables or direct tool arguments:

- `LINKEDIN_EMAIL`: LinkedIn account email/username
- `LINKEDIN_PASSWORD`: LinkedIn account password

## Usage

1. Add the server to your MCP settings configuration file:

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "python3",
      "args": ["/path/to/linkedin_login_server/server.py"],
      "env": {
        "LINKEDIN_EMAIL": "your-email@example.com",
        "LINKEDIN_PASSWORD": "your-password"
      }
    }
  }
}
```

2. Available Tools:

### login
Log in to LinkedIn using provided credentials or environment variables.

```json
{
  "name": "login",
  "arguments": {
    "email": "optional-override@example.com",
    "password": "optional-override-password"
  }
}
```

### check_login_status
Check if currently logged in to LinkedIn.

```json
{
  "name": "check_login_status",
  "arguments": {}
}
```

## Development

### Running Tests

```bash
pytest linkedin_login_server/test_server.py -v
```

### Project Structure

- `server.py`: Main MCP server implementation
- `login_page.py`: LinkedIn login page interaction logic
- `test_server.py`: Test suite
- `requirements.txt`: Python dependencies

## Error Handling

The server includes comprehensive error handling for:
- Missing credentials
- Login failures
- Network timeouts
- Browser automation issues

All errors are properly logged and returned in the tool response format.

## Security Notes

- Credentials can be provided via environment variables or direct tool arguments
- Browser runs in headless mode for security
- All browser resources are properly cleaned up after use
