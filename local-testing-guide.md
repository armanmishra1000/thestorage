# DirectDrive Local Testing Guide

This guide will help you test the complete DirectDrive flow locally, including the backend, frontend, and Cloudflare Worker.

## Prerequisites

1. MongoDB installed locally or MongoDB Atlas account
2. Node.js and npm installed
3. Python 3.10+ installed
4. Hetzner Storage-Box credentials (or a local WebDAV server for testing)
5. Wrangler CLI installed (`npm install -g wrangler`)

## Step 1: Set Up Local MongoDB

If you don't have MongoDB Atlas, you can run MongoDB locally:

```bash
# Install MongoDB (if not already installed)
# For macOS with Homebrew:
brew tap mongodb/brew
brew install mongodb-community

# Start MongoDB
brew services start mongodb-community
```

## Step 2: Set Up Backend Environment

```bash
# Navigate to the backend directory
cd /Users/nirav/untitled\ folder\ 2/DirectDrive/Backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create a .env file
cat > .env << EOL
MONGODB_URI=mongodb://localhost:27017/directdrive
HETZNER_HOST=your-storage-box.your-server.de
HETZNER_USERNAME=your-username
HETZNER_PASSWORD=your-password
HETZNER_BASE_PATH=/files
CORS_ORIGINS=*
JWT_SECRET_KEY=local-testing-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOL
```

## Step 3: Set Up Local WebDAV Server (Optional)

If you don't have access to a Hetzner Storage-Box for testing, you can set up a local WebDAV server:

```bash
# Install Node.js WebDAV server
npm install -g webdav-server

# Create a directory for files
mkdir -p /tmp/webdav-storage

# Start WebDAV server
webdav-server --port 8000 --root /tmp/webdav-storage --username test --password test
```

Then update your `.env` file:

```
HETZNER_HOST=localhost:8000
HETZNER_USERNAME=test
HETZNER_PASSWORD=test
HETZNER_BASE_PATH=/
```

## Step 4: Run the Backend

```bash
# Make sure you're in the backend directory with the virtual environment activated
cd /Users/nirav/untitled\ folder\ 2/DirectDrive/Backend
source venv/bin/activate

# Start the FastAPI server
uvicorn app.main:app --reload --port 5000
```

The backend will be available at http://localhost:5000

## Step 5: Run the Frontend

```bash
# Open a new terminal window
# Navigate to the frontend directory
cd /Users/nirav/untitled\ folder\ 2/DirectDrive/Frontend

# Install dependencies
npm install

# Start the Angular development server
ng serve
```

The frontend will be available at http://localhost:4200

## Step 6: Test the Cloudflare Worker Locally

```bash
# Open a new terminal window
# Navigate to the worker directory
cd /Users/nirav/untitled\ folder\ 2/DirectDrive/worker

# Install Wrangler if not already installed
npm install -g wrangler

# Install dependencies for local development
npm init -y
npm install miniflare --save-dev

# Create a .dev.vars file for local environment variables
cat > .dev.vars << EOL
HETZNER_USERNAME=your-username
HETZNER_PASSWORD=your-password
EOL

# Update wrangler.toml for local development
# Make sure HETZNER_HOST and HETZNER_BASE_PATH are set correctly

# Start the worker in development mode
wrangler dev --local
```

The worker will be available at http://localhost:8787

## Step 7: Testing the Complete Flow

1. **Upload a File**:
   - Open the frontend at http://localhost:4200
   - Select a file and upload it
   - Verify the upload progress is displayed
   - Note the file ID and download URL from the success message

2. **Check File Metadata**:
   - Use curl or a browser to check the file metadata:
     ```bash
     curl http://localhost:5000/api/v1/files/{file_id}/meta
     ```
   - Verify the response includes filename, size_bytes, and remote_path

3. **Download the File**:
   - If using the local worker:
     ```bash
     curl -o downloaded_file http://localhost:8787/{remote_path}
     ```
   - If testing with the frontend, click the download link
   - Verify the file downloads correctly

4. **Test Rate Limiting**:
   - Send multiple rapid requests to the upload endpoint
   - Verify that after 10 requests in a minute, you receive a 429 response

## Troubleshooting

### Backend Issues

- Check the FastAPI logs for errors
- Verify MongoDB is running: `mongo --eval "db.version()"`
- Test WebDAV connection:
  ```bash
  curl -u username:password https://your-storage-box.your-server.de/
  ```

### Frontend Issues

- Check browser console for errors
- Verify API URL in environment.ts is correct
- Test API endpoints directly with curl

### Worker Issues

- Check Wrangler logs
- Test direct WebDAV access to verify credentials
- Verify environment variables are set correctly

## Monitoring

- Backend: Watch terminal for logs and errors
- Frontend: Use browser developer tools
- Worker: Check Wrangler logs
- MongoDB: Use MongoDB Compass to inspect data

## Complete End-to-End Test Script

Here's a bash script to test the entire flow automatically:

```bash
#!/bin/bash

# Create test file
dd if=/dev/urandom of=/tmp/test_file.bin bs=1M count=10

# Upload file
echo "Uploading file..."
UPLOAD_RESPONSE=$(curl -s -X POST \
  -F "file=@/tmp/test_file.bin" \
  http://localhost:5000/api/v1/upload)

# Extract file_id and share_url
FILE_ID=$(echo $UPLOAD_RESPONSE | grep -o '"file_id":"[^"]*"' | cut -d'"' -f4)
SHARE_URL=$(echo $UPLOAD_RESPONSE | grep -o '"share_url":"[^"]*"' | cut -d'"' -f4)

echo "File uploaded with ID: $FILE_ID"
echo "Share URL: $SHARE_URL"

# Get metadata
echo "Getting metadata..."
curl -s http://localhost:5000/api/v1/files/$FILE_ID/meta

# Download file
echo "Downloading file..."
curl -s -o /tmp/downloaded_file.bin $SHARE_URL

# Compare files
echo "Comparing files..."
if cmp -s /tmp/test_file.bin /tmp/downloaded_file.bin; then
  echo "Success! Files are identical."
else
  echo "Error: Downloaded file differs from original."
fi

# Clean up
rm /tmp/test_file.bin /tmp/downloaded_file.bin
```

Save this as `test_flow.sh` and run it with `bash test_flow.sh` to test the complete flow.
