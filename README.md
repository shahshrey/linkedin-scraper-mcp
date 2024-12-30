# LinkedIn Login Server

A server that handles LinkedIn login automation using Playwright.

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

## Notes

- The browser will launch in visible mode for debugging purposes
- Each test run creates a fresh browser session
- The server uses JSON-RPC protocol for communication
