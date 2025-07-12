# DirectDrive - File Sharing MVP

A streamlined file-sharing service using Hetzner Storage-Box and Cloudflare Worker.

## Prerequisites

- Python 3.10+
- Node.js 14+ and npm
- Docker and Docker Compose
- MongoDB Atlas account
- Hetzner Storage-Box credentials

## Backend Setup

1. Navigate to the Backend directory:
   ```
   cd Backend
   ```

2. Create a `.env` file with the following variables:
   ```
   MONGODB_URI=your_mongodb_connection_string
   HETZNER_HOST=u473570-sub1.your-storagebox.de
   HETZNER_USER=u473570-sub1
   HETZNER_PASSWORD=your_password
   HETZNER_BASE_PATH=/files
   API_HOST=api.mfcnextgen.com
   PORT=5000
   CORS_ORIGINS=*
   ```

3. Start the backend server:
   ```
   # Using Docker
   docker-compose up
   
   # Or directly with Python
   pip install -r requirements.txt
   python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
   ```

4. The API will be available at http://localhost:5000

## Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   ng serve
   ```

4. The application will be available at http://localhost:4200

## Troubleshooting

### Port already in use

If port 5000 is already in use:

```
# Find the process using port 5000
netstat -ano -p TCP | findstr ":5000"  # Windows
lsof -i :5000                          # Mac/Linux

# Kill the process
taskkill /PID <PID> /F                # Windows
kill -9 <PID>                         # Mac/Linux
```

### API Connection Issues

Ensure the frontend environment is correctly pointing to the backend URL in:
- `src/environments/environment.ts` (development)
- `src/environments/environment.prod.ts` (production)

celery -A app.celery_worker.celery_app worker --loglevel=info -P solo