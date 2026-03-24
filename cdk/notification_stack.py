"""
CDK Stack for the Event-Driven Notification System.

Provisions: SQS queue + DLQ, Producer Lambda, Consumer Lambda,
SQS → Consumer event source mapping, CloudWatch log groups,
metric filters, and a DLQ depth alarm.
"""
from __future__ import annotations

import os

import aws_cdk as cdk
import aws_cdk.aws_cloudwatch as cloudwatch
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_lambda_event_sources as lambda_event_sources
import aws_cdk.aws_logs as logs
import aws_cdk.aws_sqs as sqs
from aws_cdk import aws_lambda_python_alpha as python_lambda
from constructs import Construct


class NotificationStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── SQS: DLQ ─────────────────────────────────────────────────────────
        dlq = sqs.Queue(
            self, "NotificationDLQ",
            queue_name="notification-dlq",
            retention_period=cdk.Duration.days(4),
        )

        # ── SQS: Main queue with redrive to DLQ ──────────────────────────────
        queue = sqs.Queue(
            self, "NotificationQueue",
            queue_name="notification-queue",
            visibility_timeout=cdk.Duration.seconds(30),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq,
            ),
        )

        # ── Producer Lambda ───────────────────────────────────────────────────
        producer = python_lambda.PythonFunction(
            self, "ProducerLambda",
            function_name="notification-producer",
            entry="producer",          # CDK bundles this directory
            index="handler.py",
            handler="handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            environment={
                "SQS_QUEUE_URL": queue.queue_url,
            },
            log_retention=logs.RetentionDays.TWO_WEEKS,
        )

        # Grant producer only sqs:SendMessage
        queue.grant_send_messages(producer)

        # ── Consumer Lambda ───────────────────────────────────────────────────
        consumer = python_lambda.PythonFunction(
            self, "ConsumerLambda",
            function_name="notification-consumer",
            entry="consumer",          # CDK bundles this directory
            index="handler.py",
            handler="handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            environment={
                "SES_RECIPIENT_EMAIL": os.environ["SES_RECIPIENT_EMAIL"],
                "TELEGRAM_BOT_TOKEN":  os.environ["TELEGRAM_BOT_TOKEN"],
                "TELEGRAM_CHAT_ID":    os.environ["TELEGRAM_CHAT_ID"],
            },
            log_retention=logs.RetentionDays.TWO_WEEKS,
        )

        # Grant consumer SQS receive/delete +  SES send
        queue.grant_consume_messages(consumer)
        consumer.add_to_role_policy(iam.PolicyStatement(
            actions=["ses:SendEmail"],
            resources=["*"],
        ))

        # ── Event Source Mapping: SQS → Consumer ─────────────────────────────
        consumer.add_event_source(
            lambda_event_sources.SqsEventSource(
                queue,
                report_batch_item_failures=True,
            )
        )

        # ── CloudWatch: DLQ depth alarm ───────────────────────────────────────
        dlq_depth_metric = cloudwatch.Metric(
            namespace="AWS/SQS",
            metric_name="ApproximateNumberOfMessagesVisible",
            dimensions_map={"QueueName": dlq.queue_name},
            period=cdk.Duration.minutes(1),
            statistic="Sum",
        )

        cloudwatch.Alarm(
            self, "DLQDepthAlarm",
            alarm_name="notification-dlq-depth",
            alarm_description="Fires when DLQ contains one or more messages",
            metric=dlq_depth_metric,
            threshold=0,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        cdk.CfnOutput(self, "QueueUrl", value=queue.queue_url)
        cdk.CfnOutput(self, "DLQArn", value=dlq.queue_arn)
        cdk.CfnOutput(self, "ProducerFunctionName", value=producer.function_name)
        cdk.CfnOutput(self, "ConsumerFunctionName", value=consumer.function_name)
