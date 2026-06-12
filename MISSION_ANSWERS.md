# Day 12 Lab - Câu Trả Lời Nhiệm Vụ

## Thông tin sinh viên

- Họ và tên: Nguyễn Tuấn Anh
- Mã sinh viên: 2A202600758
- Ngày thực hiện: 2026-06-12

## Part 1: Localhost vs Production

### Exercise 1.1: Các anti-pattern tìm thấy

1. API key OpenAI bị hardcode trực tiếp trong source code.
2. Database URL chứa username và password bị hardcode.
3. Chế độ debug bị gán cố định là `True`.
4. Secret key bị in ra log.
5. Không có endpoint health check để kiểm tra trạng thái ứng dụng.
6. Port bị hardcode là `8000`.
7. Host dùng `localhost` thay vì `0.0.0.0`.
8. Reload mode được bật, không phù hợp với môi trường production.

### Exercise 1.3: Bảng so sánh

| Tính năng | Develop | Production | Vì sao quan trọng? |
|---|---|---|---|
| Config | Hardcode trong source code | Đọc từ biến môi trường | Dễ deploy qua local, staging và production mà không cần sửa code |
| Secrets | Lưu trực tiếp trong code | Đọc từ env vars | Tránh lộ API key hoặc password khi push lên GitHub |
| Port | Cố định `8000` | Dùng biến môi trường `PORT` | Cloud platform thường tự cấp port khi chạy ứng dụng |
| Host | `localhost` | `0.0.0.0` | Cho phép nhận request từ bên ngoài container hoặc cloud platform |
| Health check | Không có | Có endpoint `/health` | Giúp platform monitor và restart service khi bị lỗi |
| Readiness check | Không có | Có endpoint `/ready` | Ngăn traffic đi vào app khi app chưa sẵn sàng |
| Logging | Dùng `print()` và có thể lộ secret | Dùng structured JSON logging | Dễ tìm kiếm, phân tích và debug log trong production |
| Shutdown | Không xử lý graceful shutdown | Xử lý SIGTERM và lifecycle shutdown | Tránh làm mất request khi restart hoặc deploy |

## Part 2: Docker

### Exercise 2.1: Câu hỏi về Dockerfile

1. Base image: `python:3.11`, cung cấp môi trường chạy Python cho agent.
2. Working directory: `/app`.
3. Lý do copy `requirements.txt` trước: để tận dụng Docker layer cache. Khi code thay đổi nhưng dependencies không đổi, Docker không cần cài lại toàn bộ thư viện.
4. `CMD` là lệnh mặc định khi container chạy và có thể bị override. `ENTRYPOINT` định nghĩa executable chính cố định hơn cho container.

### Exercise 2.3: So sánh kích thước image

- Develop: `agent-develop` có disk usage khoảng `1.66GB`.
- Production: `agent-production` có disk usage khoảng `236MB`.
- Difference: production image nhỏ hơn rất nhiều vì dùng multi-stage build và runtime image gọn hơn.

Stage 1 dùng để cài dependencies/build package. Stage 2 chỉ copy những thành phần cần thiết để chạy app, nên image cuối cùng không chứa nhiều build tools và cache không cần thiết.

### Exercise 2.4: Kiến trúc Docker Compose

Trong bước Quick Start, em đã build Docker image `my-agent` và chạy container trên port `8000`.

Lệnh đã dùng:

```powershell
docker build -f 02-docker/develop/Dockerfile -t my-agent .
docker run -p 8000:8000 my-agent
```

Kết quả test endpoint:

```json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Trong Exercise 2.2, em cũng build image `agent-develop` và test health check thành công:

```json
{"status":"ok","uptime_seconds":9.9,"container":true}
```

Docker Compose production stack đã chạy thành công qua Nginx ở `http://localhost`.

Kiến trúc:

```text
Client -> Nginx -> Agent -> Redis / Qdrant
```

Kết quả test `/health`:

```json
{"status":"ok","uptime_seconds":31.9,"version":"2.0.0","timestamp":"2026-06-12T08:25:54.692091"}
```

Khi gọi `/ask`, request được chuyển qua Nginx tới agent và agent trả response thành công.

## Part 3: Cloud Deployment

### Exercise 3.1: Deploy lên Railway

- URL: https://day12-agent-production-57cc.up.railway.app
- Screenshot: Chưa thêm vào repo. Có thể bổ sung ảnh Railway dashboard và ảnh test endpoint nếu giảng viên yêu cầu.

### Exercise 3.2: Render hoặc so sánh config

So sánh `railway.toml` và `render.yaml`:

| Tiêu chí | Railway | Render |
|---|---|---|
| File config | `railway.toml` | `render.yaml` |
| Cách build | Dùng Nixpacks để auto-detect Python project | Khai báo rõ `buildCommand` |
| Cách chạy app | `uvicorn app:app --host 0.0.0.0 --port $PORT` | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Env vars | Set qua Railway CLI hoặc dashboard | Khai báo trong blueprint, secret set qua dashboard hoặc generate |
| Service phụ trợ | Thường thêm qua dashboard/CLI | Có thể khai báo Redis trực tiếp trong `render.yaml` |

Railway phù hợp để deploy nhanh bằng CLI. Render phù hợp khi muốn khai báo infrastructure rõ ràng bằng YAML và đồng bộ qua GitHub.

## Part 4: API Security

### Exercise 4.1-4.3: Kết quả test

Khi gọi API không có header `X-API-Key`, hệ thống trả lỗi authentication:

```json
{"detail":"Missing API key. Include header: X-API-Key: "}
```

Khi gọi API có header `X-API-Key: my-secret-key`, request thành công và agent trả câu trả lời.

API key được kiểm tra trong logic authentication của app. Nếu thiếu hoặc sai key, service trả HTTP `401`. Để rotate key, chỉ cần đổi biến môi trường `AGENT_API_KEY` rồi restart/redeploy service, không cần sửa source code.

Với JWT authentication, em gọi endpoint `/auth/token` bằng username `student` và password `demo123` để lấy access token. Sau đó em gửi request tới `/ask` với header `Authorization: Bearer <token>` và request được xử lý thành công.

Với rate limiting, em gửi 20 request liên tiếp bằng cùng JWT token. 10 request đầu được xử lý, từ request 11 trở đi service trả HTTP `429 Too Many Requests`:

```json
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cài đặt cost guard

Cost guard được cài trong `cost_guard.py`. Trước khi gọi LLM, app gọi `cost_guard.check_budget(username)` để kiểm tra user còn budget không. Sau khi có response, app gọi `cost_guard.record_usage(...)` để cộng input tokens, output tokens, số request và chi phí ước tính.

Kết quả kiểm tra usage của user `student`:

```text
requests: 11
input_tokens: 44
output_tokens: 326
cost_usd: 0.000202
budget_usd: 1.0
budget_remaining_usd: 0.999798
```

Nếu user vượt daily budget, service sẽ trả HTTP `402 Payment Required`. Nếu global budget vượt giới hạn, service sẽ trả HTTP `503`.

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Ghi chú cài đặt

Exercise 5.1:

Em đã chạy bản `05-scaling-reliability/develop` và test các endpoint:

```json
{"status":"ok","uptime_seconds":5.9,"version":"1.0.0","environment":"development","checks":{"memory":{"status":"ok","used_percent":88.1}}}
```

Endpoint `/ready` trả:

```json
{"ready":true,"in_flight_requests":1}
```

Endpoint `/ask` trả response thành công. `/health` dùng để kiểm tra process còn sống, còn `/ready` dùng để kiểm tra app đã sẵn sàng nhận traffic chưa.

Exercise 5.2:

Khi bấm `Ctrl + C`, app shutdown đúng flow graceful shutdown. Log ghi nhận:

```text
Graceful shutdown initiated...
Shutdown complete
Application shutdown complete.
```

Điều này cho thấy app có lifecycle shutdown, chuyển trạng thái readiness và cleanup trước khi process kết thúc.

Exercise 5.3-5.5:

Em đã chạy production stack với Redis và Nginx:

```powershell
docker compose up --build --scale agent=3
```

Health check qua Nginx ở port `8080` trả:

```json
{"status":"ok","instance_id":"instance-586eaf","storage":"redis","redis_connected":true}
```

Khi gọi `/chat`, response đầu tiên có:

```text
session_id: bfc88092-3d56-47e7-a38b-99a5bb038bc9
served_by: instance-e95edd
storage: redis
```

Request tiếp theo dùng cùng `session_id` được xử lý bởi instance khác:

```text
served_by: instance-586eaf
storage: redis
```

Điều này chứng minh app stateless: conversation history không nằm trong memory riêng của từng instance, mà được lưu trong Redis. Nginx load balance request qua nhiều agent instances, nhưng session vẫn giữ được nhờ Redis.

## Part 6: Final Project - Production-ready Agent

### Mục tiêu

Ở phần final project, em hoàn thiện agent production-ready trong thư mục `06-lab-complete`. Agent kết hợp các yêu cầu chính của Day 12:

1. REST API để hỏi agent qua endpoint `/ask`.
2. API key authentication bằng header `X-API-Key`.
3. Rate limiting theo user/API key.
4. Cost guard để giới hạn chi phí LLM ước tính theo ngày.
5. Conversation history theo `user_id`.
6. Stateless design: history, rate limit và cost tracking dùng Redis khi chạy Docker Compose.
7. Health check `/health` và readiness check `/ready`.
8. Structured JSON logging.
9. Graceful shutdown với SIGTERM.
10. Dockerfile multi-stage, chạy non-root user và có HEALTHCHECK.

### Các file chính

```text
06-lab-complete/
├── app/
│   ├── main.py          # FastAPI app chính
│   ├── config.py        # Config từ environment variables
│   ├── auth.py          # API key authentication
│   ├── rate_limiter.py  # Rate limiting, ưu tiên Redis
│   └── cost_guard.py    # Budget/cost guard, ưu tiên Redis
├── utils/
│   └── mock_llm.py      # Mock LLM dùng cho lab
├── Dockerfile           # Multi-stage Dockerfile
├── docker-compose.yml   # Agent + Redis
├── .env.example
├── .dockerignore
├── railway.toml
├── render.yaml
└── check_production_ready.py
```

### Kết quả chạy local bằng Docker Compose

Em chạy final stack bằng:

```powershell
cd 06-lab-complete
docker compose up --build -d
```

Kết quả `/health`:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "staging",
  "checks": {
    "llm": "mock",
    "redis": "ok"
  }
}
```

Kết quả `/ready`:

```json
{"ready": true}
```

Khi gọi `/ask` không có API key, service trả HTTP `401`:

```json
{"detail":"Invalid or missing API key. Include header: X-API-Key."}
```

Khi gọi `/ask` có API key, service trả response thành công:

```json
{
  "user_id": "final-test",
  "question": "What is Docker?",
  "answer": "Container la cach dong goi ung dung cung dependencies de chay nhat quan o moi moi truong.",
  "model": "gpt-4o-mini",
  "history_count": 4
}
```

Endpoint `/history/final-test` xác nhận conversation history được lưu lại:

```text
count: 4
messages: user/assistant messages
```

Endpoint `/metrics` xác nhận cost guard và Redis đang hoạt động:

```json
{
  "error_count": 0,
  "cost": {
    "storage": "redis",
    "daily_budget_usd": 5.0
  },
  "rate_limit_per_minute": 20
}
```

Rate limit cũng hoạt động đúng: request 20 còn OK, request 21 bị chặn:

```json
{"detail":{"error":"Rate limit exceeded","limit":20,"window_seconds":60}}
```

### Docker image

Image final project:

```text
06-lab-complete-agent:latest
Disk usage: 247MB
Content size: 58.3MB
```

Image nhỏ hơn 500MB, đạt yêu cầu Docker của lab.

### Production readiness check

Em chạy script kiểm tra production readiness bằng Docker:

```powershell
docker run --rm -v "${PWD}:/work" -w /work day12-final-agent python check_production_ready.py
```

Kết quả:

```text
Result: 20/20 checks passed (100%)
PRODUCTION READY
```

Các nhóm yêu cầu đều pass:

1. Required files.
2. Security.
3. API endpoints.
4. Docker.
5. Multi-stage build.
6. Non-root user.
7. Health check.
8. Structured logging.

### Ghi chú deployment

Trong Quick Start, em đã deploy thành công bản Railway demo. Sau đó em deploy lại final project trong `06-lab-complete` lên cùng service Railway:

```text
https://day12-agent-production-57cc.up.railway.app
```

Kết quả kiểm tra public URL sau khi deploy final project:

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

Khi gọi `/ask` với API key, service trả response thành công:

```text
user_id: railway-final
question: What is Docker?
history_count: 2
```

Final project trong `06-lab-complete` cũng đã được kiểm tra local bằng Docker Compose và đạt production readiness 100%. Các lệnh deploy final project lên Railway:

```powershell
railway link
railway variables set AGENT_API_KEY=dev-key-change-me-in-production
railway variables set JWT_SECRET=dev-jwt-secret-change-in-production
railway variables set ENVIRONMENT=production
railway up
railway domain
```
