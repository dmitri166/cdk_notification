# Requirements Document

## Introduction

This document defines the requirements for an Event-Driven Notification System built on AWS. The system uses GitHub Actions to trigger a Producer Lambda that publishes structured event messages to Amazon SQS. A Consumer Lambda, triggered by SQS, processes those messages and dispatches notifications via AWS SES (email) and Twilio (WhatsApp). Infrastructure is fully managed by Terraform. The system includes a Dead Letter Queue, CloudWatch observability, and follows IAM least-privilege security principles.

## Glossary

- **System**: The complete event-driven notification system described in this document
- **Producer_Lambda**: The AWS Lambda function responsible for receiving event input and publishing messages to SQS
- **Consumer_Lambda**: The AWS Lambda function responsible for consuming SQS messages and dispatching notifications
- **SQS_Queue**: The Amazon SQS standard queue that buffers messages between the Producer and Consumer Lambdas
- **DLQ**: The Amazon SQS Dead Letter Queue that receives messages that fail processing after the maximum receive count
- **Notification_Dispatcher**: The component within Consumer_Lambda that sends notifications via SES and Twilio
- **Terraform**: The infrastructure-as-code tool used to provision and manage all AWS resources
- **Pipeline**: The GitHub Actions CI/CD workflow that orchestrates linting, testing, deployment, and Lambda invocation
- **Payload**: The structured JSON message published to SQS by the Producer_Lambda
- **Event_Source_Mapping**: The AWS configuration that connects SQS_Queue to Consumer_Lambda as a trigger
- **Secrets_Manager**: AWS Secrets Manager, used to store sensitive credentials such as Twilio API keys
- **CloudWatch**: AWS CloudWatch, used for logging, metrics, and alarms

---

## Requirements

### Requirement 1: Terraform Infrastructure Provisioning

**User Story:** As a DevOps engineer, I want all AWS infrastructure defined in Terraform, so that the system is reproducible, version-controlled, and deployable with a single command.

#### Acceptance Criteria

1. THE Terraform SHALL provision an SQS_Queue as a standard (non-FIFO) queue with a visibility timeout between 30 and 60 seconds.
2. THE Terraform SHALL provision a DLQ as a standard SQS queue with a `maxReceiveCount` of 3, configured as the dead-letter queue for SQS_Queue.
3. THE Terraform SHALL provision the Producer_Lambda with an IAM role granting only `sqs:SendMessage` permission on SQS_Queue.
4. THE Terraform SHALL provision the Consumer_Lambda with an IAM role granting `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `logs:*`, and `ses:SendEmail` permissions.
5. THE Terraform SHALL provision an Event_Source_Mapping that triggers Consumer_Lambda from SQS_Queue.
6. THE Terraform SHALL provision CloudWatch Log Groups for both Producer_Lambda and Consumer_Lambda.
7. THE Terraform SHALL accept all resource identifiers (queue names, function names, region) as input variables with no hardcoded ARNs or account IDs.
8. WHEN a user runs `terraform init` followed by `terraform apply`, THE Terraform SHALL successfully provision all resources without manual intervention.
9. THE Terraform SHALL expose resource ARNs and names as outputs (e.g., SQS_Queue URL, DLQ ARN, Lambda function names).

---

### Requirement 2: Producer Lambda — Event Ingestion and Publishing

**User Story:** As a pipeline operator, I want the Producer Lambda to validate and forward event payloads to SQS, so that only well-formed messages enter the system.

#### Acceptance Criteria

1. WHEN Producer_Lambda receives an invocation event, THE Producer_Lambda SHALL validate that the payload contains the fields `event_id` (string), `type` (string), `message` (string), and `timestamp` (ISO-8601 string).
2. WHEN the payload is valid, THE Producer_Lambda SHALL publish the payload as a single message to SQS_Queue.
3. IF the payload is missing a required field, THEN THE Producer_Lambda SHALL return an error response with HTTP status 400 and a descriptive message identifying the missing field.
4. IF the `timestamp` field does not conform to ISO-8601 format, THEN THE Producer_Lambda SHALL return an error response with HTTP status 400.
5. THE Producer_Lambda SHALL be stateless and SHALL NOT send any notifications directly.
6. THE Producer_Lambda SHALL NOT invoke Consumer_Lambda directly.
7. WHEN Producer_Lambda successfully publishes a message, THE Producer_Lambda SHALL return a success response containing the SQS message ID.
8. THE Producer_Lambda SHALL log each invocation result (success or failure) to its CloudWatch Log Group.

---

### Requirement 3: Consumer Lambda — Message Processing and Notification Dispatch

**User Story:** As a system operator, I want the Consumer Lambda to reliably process SQS messages and send notifications, so that stakeholders receive timely alerts for each event.

#### Acceptance Criteria

1. WHEN SQS_Queue delivers a batch of messages, THE Consumer_Lambda SHALL process each message independently.
2. WHEN processing a message with `type` equal to `"deployment"`, THE Notification_Dispatcher SHALL send an email notification via AWS SES to the configured recipient address.
3. WHEN processing a message, THE Notification_Dispatcher SHALL send a WhatsApp notification via the Twilio API to the configured recipient number.
4. IF sending an email notification fails for a specific message, THEN THE Consumer_Lambda SHALL log the failure and mark that message as failed without affecting processing of other messages in the batch.
5. IF sending a WhatsApp notification fails for a specific message, THEN THE Consumer_Lambda SHALL log the failure and mark that message as failed without affecting processing of other messages in the batch.
6. THE Consumer_Lambda SHALL be idempotent: processing the same `event_id` more than once SHALL NOT result in duplicate notifications being sent.
7. THE Consumer_Lambda SHALL log the processing result (success or failure, notification channel, `event_id`) for every message to its CloudWatch Log Group.
8. WHEN all messages in a batch are processed successfully, THE Consumer_Lambda SHALL return a success response to SQS, causing SQS to delete the messages.
9. IF a message fails processing after the maximum retry count, THEN THE Consumer_Lambda SHALL allow SQS to route that message to the DLQ.

---

### Requirement 4: SQS Queue Configuration

**User Story:** As a reliability engineer, I want SQS configured with appropriate timeouts and a DLQ, so that transient failures are retried and poison messages are isolated.

#### Acceptance Criteria

1. THE SQS_Queue SHALL be a standard queue (not FIFO).
2. THE SQS_Queue SHALL have a visibility timeout of no less than 30 seconds and no more than 60 seconds.
3. THE DLQ SHALL be configured as the redrive target for SQS_Queue with `maxReceiveCount` set to 3.
4. WHEN a message has been received and not deleted 3 times, THE SQS_Queue SHALL move that message to the DLQ.
5. THE DLQ SHALL retain failed messages for a minimum of 4 days to allow for investigation and reprocessing.

---

### Requirement 5: GitHub Actions CI/CD Pipeline

**User Story:** As a developer, I want a GitHub Actions pipeline that lints, tests, deploys infrastructure, and invokes the Producer Lambda, so that every push is validated and deployed end-to-end automatically.

#### Acceptance Criteria

1. WHEN a push is made to the configured branch, THE Pipeline SHALL check out the repository code.
2. WHEN the Pipeline runs, THE Pipeline SHALL configure AWS credentials exclusively from GitHub Secrets (no credentials in source code).
3. WHEN the Pipeline runs, THE Pipeline SHALL execute linting and unit tests for both Lambda functions before proceeding to deployment.
4. IF linting or tests fail, THEN THE Pipeline SHALL halt and SHALL NOT proceed to Terraform deployment.
5. WHEN tests pass, THE Pipeline SHALL run `terraform init` and `terraform apply` to deploy or update infrastructure.
6. WHEN Terraform apply succeeds, THE Pipeline SHALL invoke Producer_Lambda with a test event payload conforming to the Payload schema.
7. IF any Pipeline step fails, THEN THE Pipeline SHALL report the failure with a non-zero exit code.

---

### Requirement 6: Observability — Logging, Metrics, and Alarms

**User Story:** As an operations engineer, I want CloudWatch logs, metrics, and alarms configured, so that I can detect and respond to system failures in real time.

#### Acceptance Criteria

1. THE Producer_Lambda SHALL emit structured log entries to its dedicated CloudWatch Log Group for every invocation.
2. THE Consumer_Lambda SHALL emit structured log entries to its dedicated CloudWatch Log Group for every message processed.
3. THE System SHALL expose a CloudWatch metric tracking SQS_Queue depth (number of messages visible).
4. THE System SHALL expose a CloudWatch metric tracking Consumer_Lambda error count.
5. THE System SHALL expose a CloudWatch metric tracking DLQ message count.
6. WHEN the number of messages in the DLQ exceeds 0, THE System SHALL trigger a CloudWatch Alarm.
7. THE CloudWatch Alarm SHALL be provisioned and configured by Terraform.

---

### Requirement 7: Security

**User Story:** As a security engineer, I want all credentials and permissions managed securely, so that the system follows least-privilege principles and no secrets are exposed in source code.

#### Acceptance Criteria

1. THE Terraform SHALL assign each Lambda an IAM role with only the permissions listed in Requirement 1, Acceptance Criteria 3 and 4.
2. THE System SHALL store Twilio API credentials in environment variables injected at deploy time OR in Secrets_Manager, and SHALL NOT hardcode them in source code.
3. THE Pipeline SHALL retrieve AWS credentials exclusively from GitHub Secrets.
4. THE Producer_Lambda SHALL NOT have permissions to invoke Consumer_Lambda directly.
5. THE Consumer_Lambda SHALL NOT have `sqs:SendMessage` permission on SQS_Queue.
6. IF Twilio credentials are stored in Secrets_Manager, THEN THE Consumer_Lambda SHALL retrieve them at runtime via the AWS SDK and SHALL NOT log their values.

---

### Requirement 8: Payload Schema and Validation (Round-Trip)

**User Story:** As a developer, I want the Payload schema to be formally defined and validated consistently, so that malformed messages never reach the Consumer Lambda.

#### Acceptance Criteria

1. THE System SHALL define the Payload schema as: `{ "event_id": string, "type": string, "message": string, "timestamp": ISO-8601 string }`.
2. WHEN Producer_Lambda serializes a Payload to JSON for SQS, THE Producer_Lambda SHALL produce a string that, when deserialized, yields an equivalent Payload object (round-trip property).
3. WHEN Consumer_Lambda deserializes a message body from SQS, THE Consumer_Lambda SHALL produce a Payload object equivalent to the one originally serialized by Producer_Lambda.
4. IF Consumer_Lambda receives a message body that does not conform to the Payload schema, THEN THE Consumer_Lambda SHALL log the schema violation and allow the message to be routed to the DLQ after exhausting retries.

---

### Requirement 9: Dead Letter Queue Reprocessing (Optional)

**User Story:** As an operations engineer, I want a script to reprocess messages from the DLQ, so that I can recover from transient failures without data loss.

#### Acceptance Criteria

1. WHERE a DLQ reprocessing script is provided, THE System SHALL include a script that reads messages from the DLQ and republishes them to SQS_Queue.
2. WHERE a DLQ reprocessing script is provided, THE System SHALL ensure the script does not delete a message from the DLQ until it has been successfully republished to SQS_Queue.
3. WHERE a DLQ reprocessing script is provided, THE System SHALL log each reprocessed message's `event_id` and republish status.
