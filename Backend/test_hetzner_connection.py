#!/usr/bin/env python
"""
Test script to verify Hetzner Storage-Box WebDAV connection.
This script will attempt to connect to the Hetzner Storage-Box using the credentials
from environment variables and create a small test file.
"""
import os
import sys
import base64
import urllib.request
import urllib.error
import urllib.parse

# Simple function to load environment variables from .env file
def load_dotenv():
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, value = line.split('=', 1)
                os.environ[key] = value
        return True
    except Exception as e:
        print(f"Error loading .env file: {e}")
        return False

# Load environment variables from .env file
load_dotenv()

# Get credentials from environment variables
HETZNER_HOST = os.environ.get("HETZNER_HOST")
HETZNER_USER = os.environ.get("HETZNER_USER")
HETZNER_PASSWORD = os.environ.get("HETZNER_PASSWORD")
HETZNER_BASE_PATH = os.environ.get("HETZNER_BASE_PATH", "/")

# Check if credentials are available
if not all([HETZNER_HOST, HETZNER_USER, HETZNER_PASSWORD]):
    print("Error: Missing Hetzner credentials in environment variables.")
    print(f"HETZNER_HOST: {'Set' if HETZNER_HOST else 'Missing'}")
    print(f"HETZNER_USER: {'Set' if HETZNER_USER else 'Missing'}")
    print(f"HETZNER_PASSWORD: {'Set' if HETZNER_PASSWORD else 'Missing'}")
    sys.exit(1)

# Debug information
print(f"WebDAV Host: {HETZNER_HOST}")
print(f"WebDAV User: {HETZNER_USER}")
print(f"WebDAV Password length: {len(HETZNER_PASSWORD) if HETZNER_PASSWORD else 0}")
print(f"WebDAV Base Path: {HETZNER_BASE_PATH}")

# Create WebDAV URL for a test file
base_url = f"https://{HETZNER_HOST}"
test_file_path = f"{HETZNER_BASE_PATH}/test_connection.txt"
webdav_url = f"{base_url}{test_file_path}"

print(f"WebDAV URL: {webdav_url}")

# Create basic auth header
auth = base64.b64encode(f"{HETZNER_USER}:{HETZNER_PASSWORD}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "text/plain"
}

# Test content
test_content = "This is a test file to verify Hetzner Storage-Box WebDAV connection."

try:
    # Try to upload a small test file
    print("Attempting to upload test file...")
    
    # Create a PUT request
    request = urllib.request.Request(
        url=webdav_url,
        data=test_content.encode('utf-8'),
        method='PUT'
    )
    
    # Add headers
    for header, value in headers.items():
        request.add_header(header, value)
    
    try:
        # Send the request
        with urllib.request.urlopen(request) as response:
            status_code = response.getcode()
            print(f"Success! File uploaded to {webdav_url}")
            print(f"Status code: {status_code}")
            
            # Try to read the file back to verify
            print("Attempting to read the file back...")
            
            # Create a GET request
            read_request = urllib.request.Request(webdav_url)
            for header, value in headers.items():
                read_request.add_header(header, value)
            
            try:
                with urllib.request.urlopen(read_request) as read_response:
                    read_status = read_response.getcode()
                    if read_status == 200:
                        content = read_response.read().decode('utf-8')
                        print("Success! File content retrieved:")
                        print(content)
                    else:
                        print(f"Error reading file: {read_status}")
            except urllib.error.HTTPError as e:
                print(f"Error reading file: {e.code}")
                print(e.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"Error uploading file: {e.code}")
        print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Exception occurred: {str(e)}")

print("\nTroubleshooting tips:")
print("1. Verify that the HETZNER_HOST is correct (e.g., u123456-sub1.your-storagebox.de)")
print("2. Verify that the HETZNER_USER and HETZNER_PASSWORD are correct")
print("3. Make sure the HETZNER_BASE_PATH exists on the server")
print("4. Check if there are any network restrictions or firewall rules blocking the connection")
