#!/usr/bin/env python3
import aws_cdk as cdk
from notification_stack import NotificationStack

app = cdk.App()
NotificationStack(app, "NotificationStack")
app.synth()
