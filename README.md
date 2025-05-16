# ndc-gating-service

A Serverless POC that gates NDC calls by per-day failure thresholds (with departure/return dates).

## Prerequisites

- AWS CLI configured for **us-east-1**
- Node.js (v14+) & npm
- Git
- jq (for parsing JSON)

## Setup

```bash
# 1. Clone your repo
git clone https://github.com/<YOUR_GITHUB_USERNAME>/ndc-gating-service.git
cd ndc-gating-service

# 2. Initialize npm (creates package.json)
npm init -y

# 3. Install Serverless **locally** (avoid global perms issues)
npm install --save-dev serverless

# 4. (Optional) Install jq:
sudo yum install -y jq
```


## .gitignore

Create a `.gitignore` to stop tracking build artifacts:

```bash
cat > .gitignore << 'EOGI'
node_modules/
.serverless/
.env
EOGI
```

Commit it:

```bash
git add .gitignore
git commit -m "Add .gitignore"
```


## Deployment

```bash
npx serverless deploy
```

You’ll see output like:

```
POST https://<API_ID>.execute-api.us-east-1.amazonaws.com/check
POST https://<API_ID>.execute-api.us-east-1.amazonaws.com/increment
POST https://<API_ID>.execute-api.us-east-1.amazonaws.com/config
```

> Replace `<API_ID>` with your API ID.


## Seed Global Rule

```bash
aws dynamodb put-item   --table-name ndc-gating-service-dev-Config   --item '{"provider":{"S":"global"},"threshold":{"N":"10"},"enabled":{"BOOL":true}}'
```


## Usage

### 1. Check “should I call NDC?”

```bash
curl -s -X POST https://<API_ID>.execute-api.us-east-1.amazonaws.com/check   -H "Content-Type: application/json"   -d '{
    "carriers": ["AA","DL"],
    "route": "JFK-LHR",
    "tripType": "RT",
    "departureDate": "2025-06-01",
    "returnDate": "2025-06-10"
  }' | jq .
```

_Response example:_

```json
{
  "AA": { "allowNDC": true, "failCount": 0, "threshold": 10 },
  "DL": { "allowNDC": true, "failCount": 0, "threshold": 10 }
}
```


### 2. Simulate Failures

```bash
curl -s -X POST https://<API_ID>.execute-api.us-east-1.amazonaws.com/increment   -H "Content-Type: application/json"   -d '{
    "carriers": ["AA"],
    "route": "JFK-LHR",
    "tripType": "RT",
    "departureDate": "2025-06-01",
    "returnDate": "2025-06-10"
  }'
```


### 3. Update a Carrier’s Threshold

```bash
curl -s -X POST https://<API_ID>.execute-api.us-east-1.amazonaws.com/config   -H "Content-Type: application/json"   -d '{
    "provider": "AA",
    "threshold": 5,
    "enabled": true
  }'
```


## Demo Script

Create `demo.sh`:

```bash
cat > demo.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

API="https://<API_ID>.execute-api.us-east-1.amazonaws.com"
PAYLOAD='{
  "carriers": ["AA","DL"],
  "route": "JFK-LHR",
  "tripType": "RT",
  "departureDate": "2025-06-01",
  "returnDate": "2025-06-10"
}'

echo "1) Initial check"
curl -s -X POST $API/check -H "Content-Type: application/json" -d "$PAYLOAD" | jq .

echo
echo "2) Simulate 10 failures for AA"
for i in {1..10}; do
  curl -s -X POST $API/increment -H "Content-Type: application/json"     -d '{
      "carriers": ["AA"],
      "route": "JFK-LHR",
      "tripType": "RT",
      "departureDate": "2025-06-01",
      "returnDate": "2025-06-10"
    }' >/dev/null
  echo "  → increment #$i"
done

echo
echo "3) Final check"
curl -s -X POST $API/check -H "Content-Type: application/json" -d "$PAYLOAD" | jq .
EOF

chmod +x demo.sh
