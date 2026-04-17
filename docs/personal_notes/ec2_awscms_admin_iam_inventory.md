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

### 5a) `AllowManageLegacyInboundReplacementServiceRole`

**Purpose**

Add explicit access to the currently live legacy service-role path used by the
inbound replacement cutover for `ses-forwarder-role-l0ypgdpr`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowManageLegacyInboundReplacementServiceRole",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:GetRolePolicy",
        "iam:UpdateAssumeRolePolicy"
      ],
      "Resource": "arn:aws:iam::065948377733:role/service-role/ses-forwarder-role-l0ypgdpr"
    }
  ]
}
```

### 5b) `AllowManageAwsCmsServiceRoleForwarders`

**Purpose**

Future-proof role-management coverage for replacement Lambda execution roles
that live under the IAM `/service-role/` path instead of the top-level
`aws-cms-*`, `newsletter-*`, or `ses-forwarder*` role names.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowManageAwsCmsServiceRoleForwarders",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:PassRole",
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:GetRolePolicy",
        "iam:UpdateAssumeRolePolicy"
      ],
      "Resource": [
        "arn:aws:iam::065948377733:role/service-role/ses-forwarder*",
        "arn:aws:iam::065948377733:role/service-role/aws-cms-*",
        "arn:aws:iam::065948377733:role/service-role/newsletter-*"
      ]
    }
  ]
}
```

Operational note:

- these two policies close the gap between the existing top-level role patterns
  and the live SES/Lambda service-role naming used by the current inbound
  forwarder path
- they are specifically needed for pass 3, where the repo-owned inbound
  replacement updates or replaces active Lambda execution-role wiring without
  falling back to broad ad hoc IAM grants

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

Current live intent:

- queue-backed newsletter dispatch is currently hard-coded to `us-east-1`
- the canonical queue name is `aws-cms-newsletter-dispatch`
- the dispatcher Lambda consumes one queued recipient job at a time
- `news@<domain>` is the real outbound sender for newsletter delivery
- verified operator mailboxes such as `technicalContact@<domain>` act as
  newsletter authors, not the final outward sender identity

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

Current caution:

- this retirement policy does **not** authorize blind removal of the
  `aws-cms-smtp` user while AWS-CMS mailbox SMTP still depends on it
- safe immediate cleanup should focus first on legacy newsletter artifacts that
  are no longer part of the canonical control plane, such as
  `mode-c-broadcast-command` and `broadcast-command-processor`
- the shared SMTP user should only be retired after mailbox provisioning has
  fully moved away from it

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
- `service-role/ses-forwarder*`
- `service-role/aws-cms-*`
- `service-role/newsletter-*`

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
- `AllowManageLegacyInboundReplacementServiceRole`
- `AllowManageAwsCmsServiceRoleForwarders`
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
- `AllowManageLegacyInboundReplacementServiceRole`
- `AllowManageAwsCmsServiceRoleForwarders`

## Tracked cleanup target

When the mailbox flow is fully per-mailbox and the legacy shared SMTP/service-specific-credential paths are no longer used, the role should no longer need permissions scoped to:

- `arn:aws:iam::065948377733:user/aws-cms-smtp`

## Notes

- Managed policies are carrying the broad service access.
- Inline policies are being used for narrow, account-specific IAM purpose.
- This file is intended as an operational inventory and change log anchor.

---

## V2 portal, SES, and sender domains (operational contract)

**Deployment vs this inventory**

- This document describes **IAM permissions** on `EC2-AWSCMS-Admin`. It does **not** prove that a given EC2 instance has the matching **instance profile** attached, that the AWS-CMS tooling runs on that host, or that `MYCITE_V2_AWS_STATUS_FILE` on the V2 portal points at the intended live profile JSON.
- Confirm separately: instance profile attachment, working `aws sts get-caller-identity` on the tool host, and V2 `/portal/healthz` reporting `aws_config_health.live_profile_mapping: true`.

**`MYCITE_V2_AWS_STATUS_FILE`**

- V2 native portal hosts expect this env var to reference a **live** `mycite.service_tool.aws_csm.profile.v1` JSON artifact (see [instances/_shared/portal_host/app.py](../instances/_shared/portal_host/app.py) and [docs/archive/16-v2_native_portal_cutover.md](archive/16-v2_native_portal_cutover.md)).
- IAM path rules such as `arn:aws:iam::065948377733:user/aws-cms/smtp/*` govern **SMTP credential IAM users**, not which **email domain** may appear on messages. Authoritative domain policy for the portal narrow-write path is enforced in application code plus **SES identity verification**.

**SES and secondary domains (e.g. `cvccboard.org`)**

- To send as `user@cvccboard.org`, **Amazon SES** must have that address or domain **verified** in the account (and DNS in Route53 updated when using domain verification). `AmazonSESFullAccess` on this role is sufficient to *manage* identities operationally; it does not replace the verification step.
- The V2 live profile JSON may declare optional top-level `allowed_send_domains` (e.g. `["cvccboard.org"]`) in addition to `identity.domain` (e.g. `cuyahogavalleycountrysideconservancy.org`). Narrow write to `selected_verified_sender` is allowed only when the sender’s domain is in the **union** of `identity.domain` and `allowed_send_domains`. If `allowed_send_domains` is omitted, behavior matches the previous **single-domain** rule (primary domain only).
- **Rollback:** remove or narrow `allowed_send_domains` in the live profile file, revert the sender via the same narrow-write surface, or restore the profile JSON from backup/version control; IAM changes are not required for that rollback.

**IAM does not encode mailbox email domain**

- Creating IAM users under `/aws-cms/smtp/` does not assert or restrict `@domain` for SES sending. Hardening for multiple sender domains is **SES verification + V2 profile allowlist + operational review**, not an IAM path change (unless you later scope `AmazonSESFullAccess` down to explicit identity ARNs).
