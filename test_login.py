import json

# Simulate a login request
login_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "login",
        "arguments": {
            "email": "sshreyv@gmail.com",
            "password": "sPk@7x39AsnqDUM"
        }
    }
}

# Send the request to the server's stdin
print(json.dumps(login_request), flush=True)
