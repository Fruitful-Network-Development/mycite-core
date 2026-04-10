import json
import os
import urllib.request

import boto3


SES_REGION = os.environ.get("SES_REGION", "us-east-1")
CALLBACK_TOKEN = os.environ.get("CALLBACK_TOKEN", "")
ses = boto3.client("ses", region_name=SES_REGION)


def _text(value):
    return "" if value is None else str(value).strip()


def _render_text_body(content, unsubscribe_url):
    body = _text(content).rstrip()
    if body:
        body += "\n\n"
    body += f"Unsubscribe: {unsubscribe_url}\n"
    return body


def _render_html_body(content, unsubscribe_url):
    lines = [line.strip() for line in _text(content).splitlines() if line.strip()]
    if not lines:
        body = "<p>(No message body provided.)</p>"
    else:
        body = "".join(f"<p>{line}</p>" for line in lines)
    body += (
        "<hr><p style=\"font-size:0.95rem;color:#47524b\">"
        f"If you no longer want these updates, <a href=\"{unsubscribe_url}\">unsubscribe here</a>."
        "</p>"
    )
    return body


def _post_callback(callback_url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        callback_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Newsletter-Dispatch-Token": CALLBACK_TOKEN,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace").strip()
        if response.status >= 300:
            raise RuntimeError(f"callback failed with HTTP {response.status}: {body}")


def lambda_handler(event, context):
    records = list(event.get("Records") or [])
    failures = []
    for record in records:
        message_id = _text(record.get("messageId"))
        try:
            payload = json.loads(record.get("body") or "{}")
            domain = _text(payload.get("domain")).lower()
            dispatch_id = _text(payload.get("dispatch_id"))
            recipient_email = _text(payload.get("recipient_email")).lower()
            callback_url = _text(payload.get("callback_url"))
            sender_address = _text(payload.get("sender_address"))
            reply_to_address = _text(payload.get("reply_to_address"))
            subject = _text(payload.get("subject"))
            body_text = _text(payload.get("body_text"))
            unsubscribe_url = _text(payload.get("unsubscribe_url"))
            if not all([domain, dispatch_id, recipient_email, callback_url, sender_address, subject]):
                raise RuntimeError("queue payload is missing required fields")

            sent = ses.send_email(
                Source=sender_address,
                Destination={"ToAddresses": [recipient_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": _render_text_body(body_text, unsubscribe_url), "Charset": "UTF-8"},
                        "Html": {"Data": _render_html_body(body_text, unsubscribe_url), "Charset": "UTF-8"},
                    },
                },
                ReplyToAddresses=[reply_to_address] if reply_to_address else [],
            )
            _post_callback(
                callback_url,
                {
                    "domain": domain,
                    "dispatch_id": dispatch_id,
                    "email": recipient_email,
                    "status": "sent",
                    "message_id": _text(sent.get("MessageId")),
                    "queue_message_id": message_id,
                },
            )
        except Exception as exc:  # noqa: BLE001
            failures.append({"itemIdentifier": message_id or "unknown"})
            try:
                payload = json.loads(record.get("body") or "{}")
            except Exception:  # noqa: BLE001
                payload = {}
            callback_url = _text(payload.get("callback_url"))
            if callback_url:
                try:
                    _post_callback(
                        callback_url,
                        {
                            "domain": _text(payload.get("domain")).lower(),
                            "dispatch_id": _text(payload.get("dispatch_id")),
                            "email": _text(payload.get("recipient_email")).lower(),
                            "status": "failed",
                            "error": _text(exc),
                            "queue_message_id": message_id,
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass
    return {"batchItemFailures": failures}
