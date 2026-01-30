# Medical Clinic Booking System

An event-driven backend system for medical clinic bookings demonstrating SAGA choreography pattern with compensation logic.

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  CLI Client     │─────▶│  FastAPI Backend │─────▶│  External Redis │
│  (Rich UI)      │ HTTP │  (GCP Cloud Run) │ TCP  │  (Redis Cloud)  │
└─────────────────┘      └──────────────────┘      └─────────────────┘
```

### Key Components
- **Backend**: FastAPI with SAGA Choreography pattern
- **Events**: Redis Streams for event-driven decoupled messaging
- **State**: Redis for transaction state and atomic quota management
- **CLI**: Rich terminal interface with real-time SSE streaming

## 📋 Business Rules

### R1 - Discount Eligibility
Apply 12% discount if:
- User is **female** AND **today is their birthday**, OR
- Base price sum **> ₹1000**

### R2 - Daily Quota
- System-wide limit of 100 R1 discounts per day
- Resets at midnight IST
- Requests exceeding quota are rejected

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Redis (external Redis Cloud account or local)

### Local Development

```bash
# Clone the repository
git clone <repo-url>
cd EventDrivenTransaction

# Start backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
cp .env.example .env  # Edit with your Redis credentials
uvicorn app.main:app --reload --port 8080

# In another terminal, start CLI
cd cli
pip install -r requirements.txt
python main.py
```

### Using Docker

```bash
# Set Redis password
export REDIS_PASSWORD=your_redis_password

# Start with Docker Compose
docker compose up --build
```

## 🧪 Test Scenarios

### Scenario 1: Successful Birthday Discount ✅
- Female user with today as birthday
- Gets 12% discount
- Booking confirmed

### Scenario 2: Quota Exhausted ❌
- Discount quota set to max
- New discount request rejected
- Clear error message

### Scenario 3: Booking Failure with Compensation ❌
- High-value order qualifies for discount
- Quota reserved
- Booking fails (simulated)
- **Compensation releases quota**

Run scenarios via CLI menu options 2, 3, 4.

## 📚 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/services/{gender}` | Get available services |
| POST | `/booking` | Submit booking request |
| GET | `/booking/{id}/status` | Get booking status |
| GET | `/booking/{id}/stream` | SSE real-time updates |
| GET | `/admin/quota` | Get quota status |
| POST | `/admin/quota/reset` | Reset quota (testing) |

## ☁️ GCP Deployment

### Deploy to Cloud Run

```bash
cd backend

# Build and deploy
gcloud run deploy medical-booking \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars="REDIS_HOST=your-redis-host,REDIS_PORT=13962,REDIS_USERNAME=default,REDIS_PASSWORD=your-password,DAILY_DISCOUNT_QUOTA=100"
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| REDIS_HOST | Redis hostname | localhost |
| REDIS_PORT | Redis port | 6379 |
| REDIS_USERNAME | Redis username | default |
| REDIS_PASSWORD | Redis password | - |
| DAILY_DISCOUNT_QUOTA | Max daily discounts | 100 |
| DISCOUNT_PERCENTAGE | Discount percentage | 12.0 |
| HIGH_VALUE_THRESHOLD | High-value order threshold | 1000.0 |

## 📁 Project Structure

```
EventDrivenTransaction/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI application
│   │   ├── config.py         # Configuration
│   │   ├── models/           # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── saga/             # SAGA Choreography & Compensation
│   │   ├── events/           # Redis Stream Event Publisher
│   │   └── data/             # Service catalog
│   ├── Dockerfile
│   └── requirements.txt
├── cli/
│   ├── main.py               # Terminal UI
│   └── api_client.py         # HTTP client
├── docs/
│   ├── assumptions.md        # Design assumptions
│   └── test_scenarios.md     # Test documentation
└── docker-compose.yml
```

## 📝 Documentation

- [Assumptions](docs/assumptions.md) - Design decisions and constraints
- [Test Scenarios](docs/test_scenarios.md) - Detailed test case documentation

## 🎥 Video Demonstrations

1. **Terminal Demo** - All 3 test scenarios running
2. **Code Walkthrough** - Architecture explanation
3. **DevOps Logs** - Request flow and compensation logs

## 📄 License

MIT License
