# EC2-AWSCMS-Admin IAM Inventory

## Purpose

This file tracks the current IAM shape around the `EC2-AWSCMS-Admin` role, including:

- current inline policies
- attached managed policies
- deleted/replaced inline policies
- known related IAM users
- known related role name patterns
- notes on what each policy is meant to cover

## Primary role

- **Role name:** `EC2-AWSCMS-Admin`
- **Account ID:** `065948377733`
- **Role ARN:** `arn:aws:iam::065948377733:role/EC2-AWSCMS-Admin`
- **Instance profile ARN:** `arn:aws:iam::065948377733:instance-profile/EC2-AWSCMS-Admin`

## Deleted inline policies

These were removed and replaced by narrower-purpose policies.

- `AWSCMSDiagnosticsAndSmtpAccessKeyManagement`
- `AWSCMSManageSmtpCredentials`

## Current inline policies

### 1) `AWSCMSDiagnosticsLogsReadOnly`

**Purpose**

Read-only CloudWatch diagnostics for Lambda, forwarders, and related mail/newsletter flows.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowReadLambdaAndForwarderLogs",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents",
        "logs:FilterLogEvents",
        "logs:StartQuery",
        "logs:StopQuery",
        "logs:GetQueryResults"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2) `AWSCMSMailboxUsersPathManagement`

**Purpose**

Primary per-mailbox IAM user management under the IAM path `/aws-cms/smtp/`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowMailboxUserDiscovery",
      "Effect": "Allow",
      "Action": [
        "iam:ListUsers"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowMailboxAccessKeyUsageReadback",
      "Effect": "Allow",
      "Action": [
        "iam:GetAccessKeyLastUsed"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowManageMailboxUsersUnderAwsCmsSmtpPath",
      "Effect": "Allow",
      "Action": [
        "iam:CreateUser",
        "iam:DeleteUser",
        "iam:GetUser",
        "iam:UpdateUser",
        "iam:ListUserTags",
        "iam:TagUser",
        "iam:UntagUser",
        "iam:CreateAccessKey",
        "iam:DeleteAccessKey",
        "iam:UpdateAccessKey",
        "iam:ListAccessKeys",
        "iam:PutUserPolicy",
        "iam:GetUserPolicy",
        "iam:ListUserPolicies",
        "iam:DeleteUserPolicy"
      ],
      "Resource": "arn:aws:iam::065948377733:user/aws-cms/smtp/*"
    }
  ]
}
```

### 3) `AWSCMSLegacySharedSmtpAccessKeyCompatibility`

**Purpose**

Temporary compatibility for the legacy shared SMTP IAM user `aws-cms-smtp`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowInspectLegacySharedSmtpUser",
      "Effect": "Allow",
      "Action": [
        "iam:GetUser",
        "iam:ListAccessKeys"
      ],
      "Resource": "arn:aws:iam::065948377733:user/aws-cms-smtp"
    },
    {
      "Sid": "AllowManageLegacySharedSmtpAccessKeys",
      "Effect": "Allow",
      "Action": [
        "iam:CreateAccessKey",
        "iam:DeleteAccessKey",
        "iam:UpdateAccessKey"
      ],
      "Resource": "arn:aws:iam::065948377733:user/aws-cms-smtp"
    }
  ]
}
```

### 4) `AWSCMSLegacyServiceSpecificCredentialCompatibility`

**Purpose**

Temporary compatibility for the obsolete service-specific credential path on `aws-cms-smtp`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListUsersForLegacySharedSmtpDiscovery",
      "Effect": "Allow",
      "Action": [
        "iam:ListUsers"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowManageLegacyServiceSpecificCredentials",
      "Effect": "Allow",
      "Action": [
        "iam:GetUser",
        "iam:CreateServiceSpecificCredential",
        "iam:ListServiceSpecificCredentials",
        "iam:DeleteServiceSpecificCredential",
        "iam:UpdateServiceSpecificCredential"
      ],
      "Resource": "arn:aws:iam::065948377733:user/aws-cms-smtp"
    }
  ]
}
```

### 5) `AWSCMSLambdaExecutionRoleManagement`

**Purpose**

Create, update, and pass mail/newsletter Lambda execution roles.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowManageMailFlowExecutionRoles",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:GetRolePolicy",
        "iam:UpdateAssumeRolePolicy",
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::065948377733:role/aws-cms-*",
        "arn:aws:iam::065948377733:role/newsletter-*",
        "arn:aws:iam::065948377733:role/ses-forwarder*"
      ]
    }
  ]
}
```

### 6.) `AWSCMSNewsletterQueueManagement`

**Purpose**

Manage SQS queues used by newsletter delivery flows when queue-backed dispatch is enabled.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowQueueDiscovery",
      "Effect": "Allow",
      "Action": [
        "sqs:ListQueues",
        "sqs:GetQueueUrl"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowManageNewsletterQueues",
      "Effect": "Allow",
      "Action": [
        "sqs:CreateQueue",
        "sqs:DeleteQueue",
        "sqs:GetQueueAttributes",
        "sqs:SetQueueAttributes",
        "sqs:TagQueue",
        "sqs:UntagQueue",
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:PurgeQueue"
      ],
      "Resource": [
        "arn:aws:sqs:us-east-1:065948377733:newsletter-*",
        "arn:aws:sqs:us-east-1:065948377733:aws-cms-newsletter-*"
      ]
    }
  ]
}
```

### 7.) `AWSCMSLegacySharedSmtpRetirement`

**Purpose**

Provide the minimum additional IAM access needed to inspect and retire the legacy shared SMTP IAM user `aws-cms-smtp` after the hard cut to the per-mailbox model.
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowInspectLegacySharedSmtpUserForRetirement",
      "Effect": "Allow",
      "Action": [
        "iam:GetUser",
        "iam:ListAccessKeys",
        "iam:ListUserPolicies",
        "iam:GetUserPolicy",
        "iam:ListUserTags",
        "iam:ListServiceSpecificCredentials"
      ],
      "Resource": "arn:aws:iam::065948377733:user/aws-cms-smtp"
    },
    {
      "Sid": "AllowRetireLegacySharedSmtpUserArtifacts",
      "Effect": "Allow",
      "Action": [
        "iam:DeleteAccessKey",
        "iam:UpdateAccessKey",
        "iam:DeleteUserPolicy",
        "iam:DeleteServiceSpecificCredential",
        "iam:UntagUser",
        "iam:TagUser",
        "iam:DeleteUser"
      ],
      "Resource": "arn:aws:iam::065948377733:user/aws-cms-smtp"
    }
  ]
}
```

## Attached managed policies

These are attached to `EC2-AWSCMS-Admin` and provide the broader service-level access.

- `AmazonRoute53FullAccess`
- `AmazonS3FullAccess`
- `AmazonSESFullAccess`
- `AmazonSSMManagedInstanceCore`
- `AWSLambda_FullAccess`
- `CloudWatchAgentServerPolicy`
- `SecretsManagerReadWrite`

## Related IAM identities and patterns

### Legacy shared SMTP IAM user

- **User name:** `aws-cms-smtp`
- **Purpose:** legacy shared SMTP credential source
- **Status:** compatibility path only; intended to be retired after per-mailbox flow fully replaces it

### Per-mailbox SMTP IAM users

- **IAM path:** `/aws-cms/smtp/`
- **ARN pattern:** `arn:aws:iam::065948377733:user/aws-cms/smtp/*`
- **Purpose:** one SMTP credential holder per mailbox or per chosen mailbox/domain unit

### Lambda execution roles

Tracked role name patterns currently covered by inline policy:

- `aws-cms-*`
- `newsletter-*`
- `ses-forwarder*`

## Effective permission coverage by concern

### Diagnostics and investigation

Covered by:

- `AWSCMSDiagnosticsLogsReadOnly`
- `CloudWatchAgentServerPolicy`
- `AmazonSSMManagedInstanceCore`

### Mailbox IAM user lifecycle

Covered by:

- `AWSCMSMailboxUsersPathManagement`

### Legacy SMTP compatibility

Covered by:

- `AWSCMSLegacySharedSmtpAccessKeyCompatibility`
- `AWSCMSLegacyServiceSpecificCredentialCompatibility`

### Lambda-based mail and newsletter execution role lifecycle

Covered by:

- `AWSCMSLambdaExecutionRoleManagement`
- `AWSLambda_FullAccess`

### Secrets storage

Covered by:

- `SecretsManagerReadWrite`

### SES identities and sending

Covered by:

- `AmazonSESFullAccess`

### DNS and mail-routing records

Covered by:

- `AmazonRoute53FullAccess`

### S3-backed inbound or newsletter artifacts

Covered by:

- `AmazonS3FullAccess`

## Recommended lifecycle notes

### Keep now

- `AWSCMSDiagnosticsLogsReadOnly`
- `AWSCMSMailboxUsersPathManagement`
- `AWSCMSLegacySharedSmtpAccessKeyCompatibility`
- `AWSCMSLegacyServiceSpecificCredentialCompatibility`
- `AWSCMSLambdaExecutionRoleManagement`

### Remove later after hard cut from legacy shared SMTP model

- `AWSCMSLegacySharedSmtpAccessKeyCompatibility`
- `AWSCMSLegacyServiceSpecificCredentialCompatibility`

### Likely long-term retained set

- `AWSCMSDiagnosticsLogsReadOnly`
- `AWSCMSMailboxUsersPathManagement`
- `AWSCMSLambdaExecutionRoleManagement`

## Tracked cleanup target

When the mailbox flow is fully per-mailbox and the legacy shared SMTP/service-specific-credential paths are no longer used, the role should no longer need permissions scoped to:

- `arn:aws:iam::065948377733:user/aws-cms-smtp`

## Notes

- Managed policies are carrying the broad service access.
- Inline policies are being used for narrow, account-specific IAM purpose.
- This file is intended as an operational inventory and change log anchor.
