# Assumptions

This document outlines all assumptions made during the implementation of the Medical Clinic Booking System.

## Business Logic Assumptions

### User Management
1. **No Authentication Required**: The system accepts user information (name, gender, DOB) without requiring user registration or login. This is a demo system focused on the transaction workflow.

2. **Single User Identity**: Each booking request is treated as independent. There's no user account linking or history tracking.

### Service Catalog
3. **Predefined Services**: Medical services are statically defined in code with fixed pricing. In production, these would come from a database.

4. **Gender-Specific Services**: Services are categorized by gender. Some services (like General Health Checkup) overlap, while others are gender-specific.

5. **Service Availability**: All listed services are assumed to be always available. No inventory or scheduling constraints.

### Pricing Rules

6. **R1 Discount Logic**: The 12% discount applies when:
   - User is female AND today is their birthday (month + day match), OR
   - Base price sum exceeds ₹1000
   - These conditions are evaluated in IST timezone

7. **Birthday Calculation**: Birthday is checked by comparing month and day of DOB with current date in IST. Year is not considered.

8. **Discount Stacking**: Only one discount type can apply (R1). No additional discounts or promotions are considered.

### Quota Management (R2)

9. **System-Wide Quota**: The daily discount quota is global, not per-user. First-come-first-served basis.

10. **Quota Reset Time**: Quota resets at midnight IST (00:00:00 Asia/Kolkata timezone).

11. **Atomic Quota Operations**: Redis INCR is used for atomic quota reservation to prevent race conditions.

12. **Non-Discount Requests**: Requests that don't qualify for R1 discount are not counted against the quota and proceed normally.

## Technical Assumptions

### Redis Usage
13. **External Redis**: The system uses an external Redis Cloud instance for state management and event streaming.

14. **30MB Storage Limit**: Data structures are optimized for minimal storage:
    - Transaction states have 1-hour TTL
    - Event streams are trimmed to last 100 messages
    - Quota counters expire at midnight IST

15. **Redis Availability**: The system assumes Redis is available. Network failures would cause booking failures.

### Event-Driven Architecture
16. **Synchronous SAGA**: For demo purposes, the SAGA executes synchronously in a single request. In production, this would use async message queues.

17. **Single Instance**: No distributed locking is implemented. The atomic Redis operations are sufficient for single-instance deployment.

18. **Event Ordering**: Events are processed in order within a single request. Redis Streams maintain insertion order.

### Error Handling
19. **Compensation Scope**: Compensation only handles quota release. Other resources (like database records) would need additional compensation in production.

20. **Failure Simulation**: The `SIMULATE_BOOKING_FAILURE` flag is for testing only. Production would not have this feature.

21. **Retry Logic**: No automatic retries are implemented. Failed requests should be resubmitted by the user.

### API Design
22. **Immediate Response**: The booking API returns immediately with the result (synchronous processing).

23. **SSE Streaming**: Server-Sent Events are available for real-time updates but are optional. The CLI primarily uses polling.

### Deployment
24. **GCP Cloud Run**: The backend is designed for Cloud Run deployment with:
    - Stateless containers
    - External Redis for state
    - 8080 port exposure

25. **Environment Configuration**: All sensitive configuration is via environment variables, not hardcoded.

## Test Scenario Assumptions

26. **Test Data**: Test scenarios use predefined user data (Priya Sharma, Anjali Mehta, Rahul Kumar).

27. **Quota Manipulation**: Admin endpoints allow quota manipulation for testing. These should be secured in production.

28. **Failure Injection**: The failure simulation toggle affects the booking service only, not validation or pricing.

## Out of Scope

The following features are explicitly NOT implemented:

- User authentication and authorization
- Payment processing
- Appointment scheduling (date/time selection)
- Doctor assignment
- Notification system (email/SMS)
- Audit logging to external systems
- Rate limiting
- Input sanitization beyond basic validation
- Multi-region deployment
- Database persistence (all data in Redis)
