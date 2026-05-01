# CVCCBOARD.org server-side domain setup runbook

## Purpose

This runbook is for completing the `cvccboard.org` SES + Route 53 setup entirely from the server that uses the `EC2-AWSCMS-Admin` role.

It is written around the current known state:

- AWS account: `065948377733`
- IAM role on server: `EC2-AWSCMS-Admin`
- AWS region for SES/inbound mail: `us-east-1`
- Authoritative hosted zone name: `cvccboard.org`
- Authoritative hosted zone ID: `Z05968042395KDRPX4PLG`
- The root MX record has already been added to the real hosted zone
- Remaining mail-domain task: obtain the three SES DKIM CNAME records and add them to Route 53

This runbook is intentionally server-first. The process starts by inspecting the currently registered domains, hosted zones, and SES identity state from the server before making changes.

---

## What this setup is trying to achieve

The intended repeat of the existing SES-style setup is:

1. Confirm the server is really running as `EC2-AWSCMS-Admin`
2. Confirm the correct registered domain and authoritative hosted zone
3. Confirm the root MX record exists in the real hosted zone
4. Obtain SES DKIM tokens for `cvccboard.org`
5. Add the three DKIM CNAME records to Route 53
6. Confirm SES sees the DKIM records and the domain is moving toward verification
7. Clean up the duplicate hosted zone after all checks are complete

For an email-only domain, the main Route 53 records normally needed in this pattern are:

- root `MX` record for inbound SES receiving
- three SES Easy DKIM `CNAME` records

No website `A` or `www` records are needed unless the domain will also host a site.

---

## Phase 0 — confirm the server identity first

Run this before anything else.

```bash
# Run from: any directory on the EC2 server
aws sts get-caller-identity
```

Expected outcome:

- account should be `065948377733`
- the ARN should show an assumed-role session for `EC2-AWSCMS-Admin`

If this is wrong, stop. The rest of the process should not be trusted until the instance profile / credentials are corrected.

---

## Phase 1 — inspect registered domains from the server

List the registered domains in the account.

```bash
# Run from: any directory on the EC2 server
aws route53domains list-domains
```

Inspect the specific domain.

```bash
# Run from: any directory on the EC2 server
aws route53domains get-domain-detail --domain-name cvccboard.org
```

What to look for:

- the domain exists
- the domain is in the expected account
- the delegated name servers match the authoritative hosted zone

The authoritative name server set already confirmed for `cvccboard.org` is:

- `ns-148.awsdns-18.com`
- `ns-1765.awsdns-28.co.uk`
- `ns-947.awsdns-54.net`
- `ns-1225.awsdns-25.org`

That is the delegation you should continue to use.

---

## Phase 2 — inspect hosted zones from the server

List hosted zones matching `cvccboard.org`.

```bash
# Run from: any directory on the EC2 server
aws route53 list-hosted-zones-by-name --dns-name cvccboard.org
```

Inspect the authoritative hosted zone directly.

```bash
# Run from: any directory on the EC2 server
aws route53 get-hosted-zone --id /hostedzone/Z05968042395KDRPX4PLG
```

List the current records in the authoritative hosted zone.

```bash
# Run from: any directory on the EC2 server
aws route53 list-resource-record-sets --hosted-zone-id Z05968042395KDRPX4PLG
```

At this point you are checking:

- the hosted zone exists
- the authoritative zone ID is correct
- the records are being added to the real zone rather than the duplicate one

---

## Phase 3 — confirm the MX record is present

Since you already added the MX record, verify it from the authoritative hosted zone.

```bash
# Run from: any directory on the EC2 server
aws route53 list-resource-record-sets   --hosted-zone-id Z05968042395KDRPX4PLG   --query "ResourceRecordSets[?Type=='MX']"
```

The expected value for the root-domain MX record in this setup is the SES inbound endpoint for `us-east-1`.

If you need to re-check the full hosted zone contents instead:

```bash
# Run from: any directory on the EC2 server
aws route53 list-resource-record-sets --hosted-zone-id Z05968042395KDRPX4PLG --output table
```

---

## Phase 4 — inspect current SES identity state for the domain

First check whether SES already knows about the domain.

```bash
# Run from: any directory on the EC2 server
aws ses get-identity-verification-attributes   --region us-east-1   --identities cvccboard.org
```

Check DKIM status and token presence.

```bash
# Run from: any directory on the EC2 server
aws ses get-identity-dkim-attributes   --region us-east-1   --identities cvccboard.org
```

Possible outcomes:

- if DKIM tokens already exist, reuse them
- if the response is empty or the domain is not yet prepared for DKIM, generate tokens

---

## Phase 5 — obtain the three SES DKIM CNAME tokens

Generate DKIM tokens if needed.

```bash
# Run from: any directory on the EC2 server
aws ses verify-domain-dkim   --region us-east-1   --domain cvccboard.org
```

Then read the resulting tokens in a clean shape.

```bash
# Run from: any directory on the EC2 server
aws ses get-identity-dkim-attributes   --region us-east-1   --identities cvccboard.org   --query 'DkimAttributes."cvccboard.org".DkimTokens'
```

These are the three token values that become the three Route 53 `CNAME` records.

---

## Phase 6 — add the three DKIM CNAME records to Route 53

This command sequence fetches the three DKIM tokens and creates a Route 53 change batch for the authoritative hosted zone.

```bash
# Run from: any directory on the EC2 server
HZID="Z05968042395KDRPX4PLG"
DOMAIN="cvccboard.org"

read -r TOK1 TOK2 TOK3 <<< "$(aws ses get-identity-dkim-attributes   --region us-east-1   --identities "$DOMAIN"   --query 'DkimAttributes."cvccboard.org".DkimTokens'   --output text)"

cat > /tmp/cvccboard-dkim.json <<JSON
{
  "Comment": "Add SES Easy DKIM CNAME records for ${DOMAIN}",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "${TOK1}._domainkey.${DOMAIN}",
        "Type": "CNAME",
        "TTL": 1800,
        "ResourceRecords": [
          { "Value": "${TOK1}.dkim.amazonses.com" }
        ]
      }
    },
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "${TOK2}._domainkey.${DOMAIN}",
        "Type": "CNAME",
        "TTL": 1800,
        "ResourceRecords": [
          { "Value": "${TOK2}.dkim.amazonses.com" }
        ]
      }
    },
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "${TOK3}._domainkey.${DOMAIN}",
        "Type": "CNAME",
        "TTL": 1800,
        "ResourceRecords": [
          { "Value": "${TOK3}.dkim.amazonses.com" }
        ]
      }
    }
  ]
}
JSON

aws route53 change-resource-record-sets   --hosted-zone-id "$HZID"   --change-batch file:///tmp/cvccboard-dkim.json
```

After the change request is submitted, Route 53 returns a change ID. You can poll that change if needed.

```bash
# Run from: any directory on the EC2 server
CHANGE_ID="REPLACE_WITH_THE_ID_RETURNED_BY_ROUTE53"

aws route53 get-change --id "$CHANGE_ID"
```

---

## Phase 7 — verify the DKIM records now exist in Route 53

Confirm the CNAME records are present in the authoritative hosted zone.

```bash
# Run from: any directory on the EC2 server
aws route53 list-resource-record-sets   --hosted-zone-id Z05968042395KDRPX4PLG   --query "ResourceRecordSets[?Type=='CNAME']"
```

If you want to see only the DKIM CNAME rows:

```bash
# Run from: any directory on the EC2 server
aws route53 list-resource-record-sets   --hosted-zone-id Z05968042395KDRPX4PLG   --query "ResourceRecordSets[?contains(Name, '_domainkey.cvccboard.org.')]"
```

---

## Phase 8 — verify SES now sees the DKIM records

Check SES DKIM status.

```bash
# Run from: any directory on the EC2 server
aws ses get-identity-dkim-attributes   --region us-east-1   --identities cvccboard.org   --query 'DkimAttributes."cvccboard.org".{Enabled:DkimEnabled,Status:DkimVerificationStatus,Tokens:DkimTokens}'
```

What to expect:

- immediately after record creation, the status may still be pending
- after DNS propagation, SES should move the DKIM verification status toward success

You can also re-check general identity verification state.

```bash
# Run from: any directory on the EC2 server
aws ses get-identity-verification-attributes   --region us-east-1   --identities cvccboard.org
```

---

## Phase 9 — inspect SES receipt-rule dependencies if inbound processing matters

If the domain is meant to actually receive mail through SES and then process it via S3 / Lambda / SNS flows, inspect the current active receipt-rule set.

List receipt rule sets:

```bash
# Run from: any directory on the EC2 server
aws ses describe-active-receipt-rule-set --region us-east-1
```

List all rule sets if needed:

```bash
# Run from: any directory on the EC2 server
aws ses list-receipt-rule-sets --region us-east-1
```

If receipt rules do not yet cover `cvccboard.org`, that is separate from MX/DKIM DNS and may require updating the SES receipt pipeline.

---

## Phase 10 — clean up the duplicate hosted zone only after verification

Once all needed records exist in the authoritative hosted zone and you have verified the domain uses the NS set:

- `ns-148.awsdns-18.com`
- `ns-1765.awsdns-28.co.uk`
- `ns-947.awsdns-54.net`
- `ns-1225.awsdns-25.org`

you can delete the duplicate hosted zone.

First list hosted zones again and identify the duplicate zone ID.

```bash
# Run from: any directory on the EC2 server
aws route53 list-hosted-zones-by-name --dns-name cvccboard.org --output table
```

Then delete the duplicate hosted zone only after confirming it is not the authoritative one.

```bash
# Run from: any directory on the EC2 server
DUPLICATE_HZID="REPLACE_WITH_DUPLICATE_ZONE_ID"

aws route53 delete-hosted-zone --id "$DUPLICATE_HZID"
```

Do not run that command until:

- the real zone is confirmed
- the needed MX and DKIM records are present in the real zone
- there are no records worth preserving in the duplicate zone

---

## Server-first operational checklist

Use this order every time:

1. confirm server role with STS
2. inspect registered domain
3. inspect hosted zones
4. identify the authoritative hosted zone by matching delegated NS records
5. inspect current Route 53 records in that zone
6. inspect SES identity status
7. generate or retrieve DKIM tokens
8. add DKIM CNAME records to the authoritative hosted zone
9. verify Route 53 records
10. verify SES DKIM status
11. inspect receipt-rule coverage if inbound processing is required
12. remove duplicate hosted zone only after the active zone is complete

---

## One-shot command bundle for the current domain

This is the compact sequence for the current known `cvccboard.org` task.

```bash
# Run from: any directory on the EC2 server
aws sts get-caller-identity

aws route53domains get-domain-detail --domain-name cvccboard.org

aws route53 get-hosted-zone --id /hostedzone/Z05968042395KDRPX4PLG

aws route53 list-resource-record-sets --hosted-zone-id Z05968042395KDRPX4PLG --output table

aws ses get-identity-dkim-attributes   --region us-east-1   --identities cvccboard.org

aws ses verify-domain-dkim   --region us-east-1   --domain cvccboard.org

aws ses get-identity-dkim-attributes   --region us-east-1   --identities cvccboard.org   --query 'DkimAttributes."cvccboard.org".DkimTokens'
```

Then run the Route 53 UPSERT block from **Phase 6**.

---

## Notes for your AWS-CMS tool context

Because the server role already has Route 53 and SES service-level access, this workflow can be executed entirely from the server.

The point of beginning with present `Domains` and `Hosted zones` is to avoid writing records into the wrong hosted zone or acting against the wrong domain state. The domain/zone inspection is not optional in accounts where duplicate public hosted zones exist.

The safest contract for the AWS-CMS tool is:

- inspect first
- derive the real hosted zone from the actual registered-domain delegation
- inspect SES identity state
- only then create or upsert the needed records

That keeps the control flow deterministic and avoids silent drift into the wrong zone.
