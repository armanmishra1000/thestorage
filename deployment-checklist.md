# DirectDrive MVP Deployment Checklist

## Prerequisites
- [ ] Hetzner Storage-Box credentials (host, username, password, base path)
- [ ] MongoDB Atlas URI
- [ ] Render account access
- [ ] Vercel account access
- [ ] Cloudflare Workers account access
- [ ] DNS control for `mfcnextgen.com`, `api.mfcnextgen.com`, `dl.mfcnextgen.com`

## Backend Deployment (Render)
1. [ ] Push latest backend code to GitHub
2. [ ] Create new web service in Render dashboard
3. [ ] Link to GitHub repository
4. [ ] Set environment variables:
   - [ ] `MONGODB_URI`: MongoDB Atlas connection string
   - [ ] `HETZNER_HOST`: Storage-Box hostname
   - [ ] `HETZNER_USERNAME`: Storage-Box username
   - [ ] `HETZNER_PASSWORD`: Storage-Box password
   - [ ] `HETZNER_BASE_PATH`: Storage-Box base path (e.g., `/files`)
   - [ ] `CORS_ORIGINS`: Set to `*` for testing, restrict later
   - [ ] `JWT_SECRET_KEY`: Random secure string
   - [ ] `JWT_ALGORITHM`: `HS256`
   - [ ] `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: `1440` (24 hours)
5. [ ] Deploy service
6. [ ] Verify `/healthz` endpoint returns 200 OK

## Cloudflare Worker Deployment
1. [ ] Install Wrangler CLI: `npm install -g wrangler`
2. [ ] Login to Wrangler: `wrangler login`
3. [ ] Navigate to worker directory: `cd worker`
4. [ ] Set secrets:
   - [ ] `wrangler secret put HETZNER_USERNAME`
   - [ ] `wrangler secret put HETZNER_PASSWORD`
5. [ ] Update `wrangler.toml` with correct values:
   - [ ] `HETZNER_HOST`
   - [ ] `HETZNER_BASE_PATH`
6. [ ] Deploy worker: `wrangler publish`
7. [ ] Test worker with curl: `curl -I https://dl.mfcnextgen.com/<test-file>`
8. [ ] Verify headers include `Cache-Control: public, max-age=604800`
9. [ ] Test Range request support: `curl -I -H "Range: bytes=0-1023" https://dl.mfcnextgen.com/<test-file>`

## Frontend Deployment (Vercel)
1. [ ] Push latest frontend code to GitHub
2. [ ] Create new project in Vercel dashboard
3. [ ] Link to GitHub repository
4. [ ] Set environment variables if needed
5. [ ] Deploy project
6. [ ] Verify frontend loads correctly
7. [ ] Test file upload functionality
8. [ ] Test file download functionality

## DNS Configuration
1. [ ] Configure `api.mfcnextgen.com` to point to Render service
2. [ ] Configure `dl.mfcnextgen.com` to point to Cloudflare Worker
3. [ ] Configure `mfcnextgen.com` to point to Vercel deployment
4. [ ] Verify all domains resolve correctly

## Final Smoke Tests
1. [ ] Upload a 1GB file from Chrome
   - [ ] Monitor RAM/CPU usage on Render (should stay <512MB RAM, <100% CPU)
   - [ ] Verify upload completes successfully
2. [ ] Download the same file via `dl.mfcnextgen.com`
   - [ ] Verify correct filename
   - [ ] Verify download resume works
3. [ ] Check metadata endpoint
   - [ ] `GET /api/v1/files/<id>/meta` returns correct information
4. [ ] Test rate limiting
   - [ ] 10 uploads/minute from one IP should yield HTTP 429
5. [ ] Check Hetzner panel for storage usage
6. [ ] Run tests with a small test cohort (10 people)
   - [ ] Collect feedback
   - [ ] Address any issues

## Post-Deployment
1. [ ] Monitor error logs in Render
2. [ ] Monitor worker analytics in Cloudflare
3. [ ] Set up alerts for high resource usage
4. [ ] Document any issues or improvements for future phases
