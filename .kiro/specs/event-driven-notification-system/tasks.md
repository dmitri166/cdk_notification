# Implementation Plan: Event-Driven Notification System

## Overview

Implement a serverless AWS notification pipeline in Python 3.12. The Producer Lambda validates and enqueues payloads to SQS; the Consumer Lambda dequeues and dispatches notifications via SES and Twilio. All infrastructure is managed by Terraform and deployed via GitHub Actions.

## Tasks

- [-] 1. Define project structure and shared Payload schema
  - Create directory layout: `producer/`, `consumer/`, `terraform/`, `.github/workflows/`
  - Define the `Payload` dataclass/TypedDict and `validate_payload()` function in a shared `schema.py` module
  - Implement ISO-8601 timestamp validation helper
  - _Requirements: 2.1, 8.1_

  - [ ] 1.1 Write property test for payload validator (Property 1)
    - **Property 1: Payload Validation Accepts Valid and Rejects Invalid Inputs**
    - **Validates: Requirements 2.1, 2.3, 2.4, 8.1**
    - Use `hypothesis` to generate valid payloads (assert accepted) and invalid payloads with missing/malformed fields (assert rejected with 400)
    - Tag: `# Feature: event-driven-notification-system, Property 1`

  - [ ] 1.2 Write property test for payload round-trip serialization (Property 3)
    - **Property 3: Payload Serialization Round-Trip**
    - **Validates: Requirements 8.2, 8.3**
    - Use `hypothesis` to generate valid payloads; assert `json.loads(json.dumps(payload)) == payload`
    - Tag: `# Feature: event-driven-notification-system, Property 3`

- [ ] 2. Implement Producer Lambda
  - [x] 2.1 Implement `producer/handler.py` with `handler(event, context)`
    - Call `validate_payload()` from shared schema module
    - On valid payload: call `sqs_client.send_message()` and return `{ statusCode: 200, body: { messageId } }`
    - On invalid payload: return `{ statusCode: 400, body: { error, field } }`
    - Emit structured CloudWatch log entry for every invocation result
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ] 2.2 Write property test for Producer Lambda publishes exactly one SQS message (Property 2)
    - **Property 2: Valid Payload Produces Exactly One SQS Message**
    - **Validates: Requirements 2.2, 2.7**
    - Mock `sqs_client.send_message`; use `hypothesis` to generate valid payloads; assert exactly one call with serialized body
    - Tag: `# Feature: event-driven-notification-system, Property 2`

  - [ ] 2.3 Write unit tests for Producer Lambda
    - Test missing each required field returns 400 with correct field name
    - Test malformed timestamp returns 400
    - Test SQS failure returns 500 and logs error
    - _Requirements: 2.3, 2.4, 2.8_

- [ ] 3. Implement Consumer Lambda — core processing loop
  - [x] 3.1 Implement `consumer/handler.py` with `handler(event, context)`
    - Iterate over `event["Records"]`; deserialize and validate each record body using shared schema
    - For invalid bodies: log schema violation, add `messageId` to `batchItemFailures`, continue
    - Return `{ batchItemFailures: [...] }`
    - _Requirements: 3.1, 8.3, 8.4_

  - [ ] 3.2 Write property test for invalid SQS message body handling (Property 4)
    - **Property 4: Invalid SQS Message Body Triggers Schema Violation Logging**
    - **Validates: Requirements 8.4**
    - Use `hypothesis` to generate invalid record bodies; assert schema violation logged and record in `batchItemFailures`
    - Tag: `# Feature: event-driven-notification-system, Property 4`

- [ ] 4. Implement Notification Dispatcher module
  - [x] 4.1 Implement `consumer/dispatcher.py` with `dispatch_email(payload)` and `dispatch_whatsapp(payload)`
    - `dispatch_email`: call `ses_client.send_email()` only when `payload.type == "deployment"`
    - `dispatch_whatsapp`: call Twilio API for all messages
    - Each function returns a `Result` (success/failure) without raising; failures are caught and returned
    - Retrieve Twilio credentials from environment variables (or Secrets Manager at runtime)
    - _Requirements: 3.2, 3.3, 7.2, 7.6_

  - [ ] 4.2 Write property test for notification dispatch by message type (Property 6)
    - **Property 6: Notification Dispatch by Message Type**
    - **Validates: Requirements 3.2, 3.3**
    - Mock SES and Twilio clients; use `hypothesis` to generate messages with random types; assert SES called iff `type=deployment`, Twilio always called once
    - Tag: `# Feature: event-driven-notification-system, Property 6`

  - [ ] 4.3 Write unit tests for Notification Dispatcher
    - Test SES called with correct arguments for `type=deployment`
    - Test SES not called for other types
    - Test Twilio called for all message types
    - Test SES failure returns failure Result without raising
    - Test Twilio failure returns failure Result without raising
    - _Requirements: 3.2, 3.3, 3.4, 3.5_

- [ ] 5. Wire dispatcher into Consumer Lambda with fault isolation and idempotency
  - [x] 5.1 Integrate `dispatcher.py` into `consumer/handler.py`
    - Call `dispatch_email` and `dispatch_whatsapp` per record; on failure log and add to `batchItemFailures`
    - Implement in-memory idempotency set: skip dispatch and log duplicate if `event_id` already seen
    - Log processing result (success/failure, channel, `event_id`) for every message
    - _Requirements: 3.1, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ]* 5.2 Write property test for batch fault isolation (Property 5)
    - **Property 5: Batch Processing Independence (Fault Isolation)**
    - **Validates: Requirements 3.1, 3.4, 3.5**
    - Use `hypothesis` to generate batches with random failure injection; assert only failed records appear in `batchItemFailures`
    - Tag: `# Feature: event-driven-notification-system, Property 5`

  - [ ]* 5.3 Write property test for Consumer idempotence (Property 7)
    - **Property 7: Consumer Idempotence**
    - **Validates: Requirements 3.6**
    - Use `hypothesis` to generate `event_id` values; process same message twice; assert dispatch called at most once per `event_id`
    - Tag: `# Feature: event-driven-notification-system, Property 7`

  - [ ]* 5.4 Write property test for successful batch returns empty batchItemFailures (Property 8)
    - **Property 8: Successful Batch Returns Empty batchItemFailures**
    - **Validates: Requirements 3.8**
    - Use `hypothesis` to generate fully successful batches; assert `batchItemFailures` is empty
    - Tag: `# Feature: event-driven-notification-system, Property 8`

  - [ ]* 5.5 Write property test for logging completeness (Property 9)
    - **Property 9: Logging Completeness**
    - **Validates: Requirements 2.8, 3.7, 6.1, 6.2**
    - Use `hypothesis` to generate any valid/invalid input for both lambdas; assert structured logger called with result including `event_id`, channel, and status
    - Tag: `# Feature: event-driven-notification-system, Property 9`

- [ ] 6. Checkpoint — Ensure all Lambda unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Provision Terraform infrastructure
  - [x] 7.1 Create `terraform/modules/sqs/main.tf`
    - Define `aws_sqs_queue` (standard, `visibility_timeout_seconds` in [30,60]) and DLQ with `maxReceiveCount=3` and 4-day retention
    - Parameterise queue names and region as input variables; expose queue URL and DLQ ARN as outputs
    - _Requirements: 1.1, 1.2, 1.7, 1.9, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 7.2 Write property test for SQS visibility timeout bounds (Property 11)
    - **Property 11: SQS Visibility Timeout Within Bounds**
    - **Validates: Requirements 1.1, 4.2**
    - Parse `terraform/modules/sqs/main.tf`; assert `visibility_timeout_seconds` is an integer in [30, 60]
    - Tag: `# Feature: event-driven-notification-system, Property 11`

  - [x] 7.3 Create `terraform/modules/lambda/main.tf`
    - Define Producer Lambda (Python 3.12) with IAM role granting only `sqs:SendMessage` on SQS_Queue
    - Define Consumer Lambda (Python 3.12) with IAM role granting `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `logs:*`, `ses:SendEmail`, and optionally `secretsmanager:GetSecretValue`
    - Define Event Source Mapping connecting SQS_Queue to Consumer Lambda
    - Parameterise all names and ARNs; expose Lambda function names as outputs
    - _Requirements: 1.3, 1.4, 1.5, 1.7, 1.9, 7.1, 7.4, 7.5_

  - [x] 7.4 Create `terraform/modules/observability/main.tf`
    - Define CloudWatch Log Groups for both Lambdas
    - Define metric filters for SQS queue depth, Consumer Lambda error count, and DLQ message count
    - Define CloudWatch Alarm that fires when DLQ depth > 0
    - _Requirements: 1.6, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 7.5 Create `terraform/main.tf` root module
    - Wire `sqs`, `lambda`, and `observability` modules together
    - Accept all resource identifiers as input variables with no hardcoded ARNs or account IDs
    - Expose all required outputs (queue URL, DLQ ARN, Lambda names)
    - _Requirements: 1.7, 1.8, 1.9_

- [ ] 8. Implement GitHub Actions CI/CD pipeline
  - [x] 8.1 Create `.github/workflows/deploy.yml`
    - Job `lint-and-test`: checkout → configure AWS credentials from GitHub Secrets → lint (`flake8`/`ruff`) → run unit and property tests
    - Job `deploy` (needs: lint-and-test): `terraform init` → `terraform apply`
    - Job `smoke-test` (needs: deploy): invoke Producer Lambda with valid test payload (assert 200); invoke with invalid payload (assert 400)
    - Ensure any step failure halts the pipeline with non-zero exit code
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 7.3_

- [ ] 9. Security hardening — verify no hardcoded credentials
  - [ ] 9.1 Write property test for no hardcoded credentials in source (Property 10)
    - **Property 10: No Hardcoded Credentials in Source**
    - **Validates: Requirements 7.2, 5.2**
    - Scan all `.py`, `.tf`, and `.yml` files for patterns matching Twilio API keys, AWS secret keys, or account IDs; assert no matches
    - Tag: `# Feature: event-driven-notification-system, Property 10`

- [ ] 10. Implement optional DLQ reprocessing script
  - [x] 10.1 Create `scripts/reprocess_dlq.py`
    - Read messages from DLQ via `sqs:ReceiveMessage`
    - For each message: call `sqs:SendMessage` to SQS_Queue; only call `sqs:DeleteMessage` on DLQ after successful send
    - Log each reprocessed message's `event_id` and republish status
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 10.2 Write property test for DLQ reprocessing safety (Property 12)
    - **Property 12: DLQ Reprocessing Safety**
    - **Validates: Requirements 9.2**
    - Simulate send failures; assert `sqs:DeleteMessage` is never called before a successful `sqs:SendMessage`
    - Tag: `# Feature: event-driven-notification-system, Property 12`

- [ ] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use `hypothesis` (Python); run a minimum of 100 iterations each
- Each property test is tagged with `# Feature: event-driven-notification-system, Property <N>`
- Checkpoints ensure incremental validation before moving to the next phase
- All Terraform resource names, ARNs, and region must remain parameterised — no hardcoded values
