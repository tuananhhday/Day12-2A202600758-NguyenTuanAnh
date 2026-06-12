# Deployment Information

## Public URL

https://day12-agent-production-57cc.up.railway.app

## Platform

Railway

Note: This public URL now points to the final project deployed from `06-lab-complete`.

## Test Commands

### Health Check

```powershell
curl.exe --ssl-no-revoke https://day12-agent-production-57cc.up.railway.app/health
```

### API Test

```powershell
Invoke-RestMethod `
  -Uri "https://day12-agent-production-57cc.up.railway.app/ask" `
  -Method Post `
  -Headers @{"X-API-Key"="dev-key-change-me-in-production"} `
  -ContentType "application/json" `
  -Body '{"user_id":"railway-final","question":"Hello"}'
```

## Environment Variables Set

- PORT
- AGENT_API_KEY
- JWT_SECRET
- ENVIRONMENT

`REDIS_URL` is used in local Docker Compose. Railway currently runs without Redis attached, so `/health` reports `redis: not_configured`.

## Notes

The Railway final deployment passed the platform health check and returned a valid response from the `/ask` endpoint.

Railway health check response:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "checks": {
    "llm": "mock",
    "redis": "not_configured"
  }
}
```

Railway authenticated `/ask` response:

```text
user_id: railway-final
question: What is Docker?
answer: Container la cach dong goi ung dung cung dependencies de chay nhat quan o moi moi truong.
model: gpt-4o-mini
history_count: 2
```

The final production agent was verified locally:

- `/health` returns `status: ok`
- `/ready` returns `ready: true`
- `/ask` returns `401` without API key
- `/ask` works with `X-API-Key`
- Conversation history is stored by `user_id`
- Redis-backed metrics report `storage: redis`
- Rate limit returns `429` after the configured limit
- Docker image size is about `247MB`
- `check_production_ready.py` passed `20/20` checks

## Final Project Local Test Commands

```powershell
cd F:\Day12-2A202600758-NguyenTuanAnh\06-lab-complete
docker compose up --build -d
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/ready
```

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/ask" `
  -Method Post `
  -Headers @{"X-API-Key"="dev-key-change-me-in-production"} `
  -ContentType "application/json" `
  -Body '{"user_id":"final-test","question":"What is Docker?"}'
```

## Final Project Railway Deploy Commands

```powershell
cd F:\Day12-2A202600758-NguyenTuanAnh\06-lab-complete
railway link
railway variables set AGENT_API_KEY=dev-key-change-me-in-production
railway variables set JWT_SECRET=dev-jwt-secret-change-in-production
railway variables set ENVIRONMENT=production
railway up
railway domain
```

## Screenshots

Add the required submission screenshots here:

- Deployment dashboard: `screenshots/dashboard.png`
- Service running / public health check: `screenshots/health.png`
- Authenticated API test result: `screenshots/api-test.png`

These screenshots should show the Railway service online and the public URL responding successfully.
