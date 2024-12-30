# LinkedIn Login Server

A server that handles LinkedIn login automation using Playwright.

## Project Structure

```
├── server.py           # Main server implementation
├── login_page.py       # LinkedIn login page automation
├── profile_page.py     # Profile page interaction logic
├── requirements.txt    # Project dependencies
├── pytest.ini         # PyTest configuration
└── .gitignore         # Git ignore rules
```

## Prerequisites

- Python 3.x
- Virtual environment (recommended)

## Dependencies

The project requires the following Python packages:
- playwright - Browser automation
- pytest - Testing framework
- pytest-asyncio - Async testing support
- pytest-playwright - Playwright testing integration
- mcp - Custom package
- beautifulsoup4 - HTML parsing
- lxml - XML/HTML processing

## Setup

1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

## Local Testing

You can test the server locally using the provided test scripts:

1. Login Test:
```bash
python3 test_login.py | python3 server.py
```
This will launch a browser and attempt to log in to LinkedIn with the provided credentials.

2. Login Status Check:
```bash
python3 test_status.py | python3 server.py
```
This will launch a browser and check if you're currently logged in to LinkedIn.

## Expected Output

### Successful Login
```
INFO:__main__:Starting linkedin-login-server
INFO:__main__:Browser session initialized
INFO:login_page:Navigating to LinkedIn login page
INFO:login_page:Waiting for redirect to feed page
INFO:login_page:Login successful
```

### Status Check
```
INFO:__main__:Starting linkedin-login-server
INFO:__main__:Browser session initialized
```

## Troubleshooting

If you don't see the browser:
1. Ensure you have Playwright installed and configured
2. Check that the server is running with `headless=False`
3. Look for any error messages in the console output

## Development Notes

- The browser will launch in visible mode for debugging purposes
- Each test run creates a fresh browser session
- The server uses JSON-RPC protocol for communication
- All major components are separated into individual modules for better maintainability
- Error handling is implemented with descriptive logging throughout the application
