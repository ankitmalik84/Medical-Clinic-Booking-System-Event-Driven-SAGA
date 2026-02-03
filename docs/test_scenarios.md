# Test Scenarios

This document describes the three required test scenarios demonstrating the event-driven transaction workflow.

---

## Test Scenario 1: Successful Birthday Discount Booking ✅

### Description
A female user whose birthday is today successfully books multiple medical services and receives the 12% R1 discount.

### Preconditions
- Quota is not exhausted (< 100 discounts used today)
- Failure simulation is disabled

### Input Data
| Field | Value |
|-------|-------|
| Name | Priya Sharma |
| Gender | Female |
| Date of Birth | Today's date (2026-01-29) |
| Services | General Health Checkup (₹500), Mammography (₹700) |

### Expected Flow
1. **Booking Initiated** → Request received and state created
2. **Validation Started** → Validating user input
3. **Validation Completed** → User data and services validated
4. **Pricing Started** → Calculating base price
5. **Pricing Completed** → Base: ₹1200, R1 eligible (birthday)
6. **Quota Check Started** → Checking discount availability
7. **Quota Reserved** → Discount slot reserved (e.g., slot 1/100)
8. **Booking Started** → Creating booking record
9. **Booking Completed** → Reference ID generated

### Expected Result
```
✅ BOOKING CONFIRMED

Reference: BK-20260129-XXXX
Base Price: ₹1,200
Discount: 12% (Birthday discount - Female)
Final Price: ₹1,056

Services booked:
  • General Health Checkup
  • Mammography
```

### What This Demonstrates
- Complete SAGA workflow execution
- R1 discount eligibility check (female + birthday)
- Quota reservation (atomic Redis operation)
- Successful transaction completion

---

## Test Scenario 2: Quota Exceeded + Compensation (Revert Committed Reserve) ❌

### Description
A female user whose birthday is today attempts to book, but the daily discount quota has already been exhausted. The system **commits** a quota reserve (atomic INCR) and then detects over-limit; SAGA treats this as a failure and **compensation reverts** the committed reserve by releasing the slot (DECR). This satisfies: *"compensation logic for quota exceeds reverts something that has been committed earlier."*

### Preconditions
- Quota set to maximum (100/100 discounts used)
- Failure simulation is disabled

### Setup Steps
```bash
# Set quota to max so next R1-eligible booking hits quota exceeded
curl -X POST http://localhost:8080/admin/quota/set/100
```

### Input Data
| Field | Value |
|-------|-------|
| Name | Anjali Mehta |
| Gender | Female |
| Date of Birth | Today's date |
| Services | General Health Checkup (₹500) |

### Expected Flow
1. **Booking Initiated** → Request received
2. **Validation Completed** → User data validated
3. **Pricing Completed** → Base: ₹500, R1 eligible (birthday)
4. **Quota Check Started** → Checking discount availability
5. **Quota slot reserved (over limit)** → Reserve first (INCR committed); slot reserved over limit
6. **Quota exceeded** → Check fails; request rejected
7. **Transaction Failed** → SAGA marks transaction as failed
8. **Compensation Started** → Compensation logic triggered
9. **Compensation Completed** → **Quota released** (DECR reverts the committed reserve)

### Expected Result
```
❌ BOOKING FAILED

Reason: Daily discount quota reached. Please try again tomorrow.

Request ID: XXXXXXXX
```

Terminal must show: **"Compensation completed. Actions: Quota released"** (and quota count back to 100 after the demo).

### What This Demonstrates
- **Technical Requirement 1.d**: SAGA choreography pattern with compensation logic — same failure path for all failures, compensation handler reverts committed work.
- **Compensation for quota exceeds**: Something was **committed** (the over-limit quota slot via INCR); compensation **reverts** it (release_quota does DECR). Order: commit first, then failure, then compensation reverts.
- Quota exhaustion handling and proper rejection message
- System-wide quota enforcement

### Verification
After the failure, quota must return to the pre-request value (e.g. 100):
```bash
curl http://localhost:8080/admin/quota
# current_count should be 100 (the over-reserve was reverted)
```

---

## Test Scenario 3: Booking Failure with Compensation ❌

### Description
A high-value order qualifies for R1 discount, quota is reserved, but the booking service fails. Compensation must release the reserved quota.

### Preconditions
- Quota is available (reset to 0)
- Failure simulation is ENABLED

### Setup Steps
```bash
# Reset quota and enable failure simulation
curl -X POST http://localhost:8080/admin/quota/reset
curl -X POST http://localhost:8080/admin/simulate-failure -H "Content-Type: application/json" -d '{"enable": true}'
```

### Input Data
| Field | Value |
|-------|-------|
| Name | Rahul Kumar |
| Gender | Male |
| Date of Birth | 1990-05-15 (not birthday) |
| Services | General Health Checkup (₹500), Cardiac Screening (₹800), Prostate Examination (₹600) |

### Expected Flow
1. **Booking Initiated** → Request received
2. **Validation Completed** → User data validated
3. **Pricing Completed** → Base: ₹1900 (>₹1000), R1 eligible (high-value)
4. **Quota Check Started** → Checking discount availability
5. **Quota Reserved** → Discount slot reserved (slot 1/100)
6. **Booking Started** → Creating booking record
7. **Booking Failed** → Simulated failure occurs
8. **Compensation Started** → Triggering rollback
9. **Compensation Completed** → Quota released

### Expected Result
```
❌ BOOKING FAILED

Reason: Booking failed: Simulated booking failure for testing

Request ID: XXXXXXXX
```

### What This Demonstrates
- **SAGA Compensation Pattern**: When booking fails after quota reservation, the system automatically releases the quota
- **Audit Trail**: All events including compensation are logged
- **Resource Cleanup**: No orphaned quota reservations

### Verification
After the failure, check quota status:
```bash
curl http://localhost:8080/admin/quota
# Response: {"current_count": 0, ...}  <- Quota was released
```

---

## Event Trace Summary

### Successful Transaction (Scenario 1)
```
booking.initiated → validation.started → validation.completed →
pricing.started → pricing.completed → quota.check_started →
quota.reserved → booking.started → booking.completed
```

### Quota Exceeded + Compensation (Scenario 2)
```
booking.initiated → validation.started → validation.completed →
pricing.started → pricing.completed → quota.check_started →
quota.reserved_over_limit (reserve first) → quota.exhausted (check fails) →
(failure) → compensation.started → compensation.completed (Quota released)
```

### Compensated Transaction (Scenario 3)
```
booking.initiated → validation.started → validation.completed →
pricing.started → pricing.completed → quota.check_started →
quota.reserved → booking.started → booking.failed →
compensation.started → compensation.completed
```

---

## Running the Scenarios

### Using the CLI

```bash
# Start the backend
cd backend
uvicorn app.main:app --reload --port 8080

# In another terminal, run the CLI
cd cli
python main.py

# Select from menu:
# 2 - Test Scenario 1 (Birthday discount)
# 3 - Test Scenario 2 (Quota exhausted)
# 4 - Test Scenario 3 (Booking failure)
```

### Using cURL

```bash
# Scenario 1: Birthday discount
curl -X POST http://localhost:8080/booking \
  -H "Content-Type: application/json" \
  -d '{
    "user": {
      "name": "Priya Sharma",
      "gender": "female",
      "date_of_birth": "1995-01-29"
    },
    "service_ids": ["f1", "f2"]
  }'
```

---

## Log Output Examples

### Successful Transaction Log
```json
{"timestamp": "2026-01-29T10:30:00", "level": "INFO", "message": "SAGA started: ABC123", "user": "Priya Sharma"}
{"timestamp": "2026-01-29T10:30:01", "level": "INFO", "message": "Validation completed: ABC123", "services": ["General Health Checkup", "Mammography"]}
{"timestamp": "2026-01-29T10:30:02", "level": "INFO", "message": "R1 discount eligible: ABC123", "reason": "Birthday discount (Female)"}
{"timestamp": "2026-01-29T10:30:03", "level": "INFO", "message": "Quota reserved: ABC123", "slot": 1, "final_price": 1056}
{"timestamp": "2026-01-29T10:30:04", "level": "INFO", "message": "Booking completed: ABC123", "reference_id": "BK-20260129-XXXX"}
{"timestamp": "2026-01-29T10:30:04", "level": "INFO", "message": "SAGA completed successfully: ABC123"}
```

### Compensation Log
```json
{"timestamp": "2026-01-29T10:35:00", "level": "INFO", "message": "SAGA started: DEF456"}
{"timestamp": "2026-01-29T10:35:03", "level": "INFO", "message": "Quota reserved: DEF456", "slot": 1}
{"timestamp": "2026-01-29T10:35:04", "level": "ERROR", "message": "Booking failed: DEF456", "error": "Simulated booking failure"}
{"timestamp": "2026-01-29T10:35:04", "level": "INFO", "message": "Starting compensation: DEF456", "quota_reserved": true}
{"timestamp": "2026-01-29T10:35:05", "level": "INFO", "message": "Quota released successfully: DEF456"}
{"timestamp": "2026-01-29T10:35:05", "level": "INFO", "message": "Compensation completed: DEF456", "actions": ["Quota released"]}
```
