# Current workflow is incorrect, not faulted, needs fixing.

## Inquery:
Consider this email I sent as `technicalContact@trappfamilyfarm.com` to `news@trappfamilyfarm.com`.
My goal was to have to workflow then send an email to the entries of contacts list that were subscribed.
This want to meant o be possible by specifying in the portal, which email (from the same domain), that it would recieve emails from to initiate the sending of news letters.
The test was meant to have `technicalContact@trappfamilyfarm.com` be the email that `news@trappfamilyfarm.com` would except written newsletters from to send out.
However, the other attached email, is the one that was received upon the agents completion of this the task.

Consider where the logic is not aligned for this to be the case.


## Response:
Sending a normal email from the technical‑contact mailbox to the `news@…` address does not trigger the queue‑backed newsletter loop, because there is no inbound monitor that treats arbitrary mail to `news@…` as a newsletter.

The queue/Lambda path is invoked only through the portal’s “newsletter‑admin” tool.  When an admin submits a newsletter, the portal resolves the verified sender, queues one message per subscribed contact and sends the bulk messages via the `newsletter‑dispatcher` Lambda.  In that process the portal itself sends a *copy* of the newsletter from the selected author (`technicalContact@domain`) to the list address (`news@domain`) using SES.  This step exists so the author can keep a copy of what was sent; it is *not* a trigger.  The plan document explicitly describes the live flow as “portal submit → SES copy from `technicalContact` to `news@domain` → one SQS message per subscribed contact → Lambda sends from `news@domain`”.  No part of the code watches for random incoming mail to `news@…` and turns it into a newsletter.

By contrast, the second attached email shows the actual queue‑driven newsletter for CVCC.  It originated from the dispatcher Lambda, not from your manual test, and it uses the proper sender and unsubscribe link.  That illustrates the intended workflow: the newsletter must be submitted through the portal with a verified sender selected, and the system will then queue and dispatch to subscribers.  If you simply send a message from `technicalContact@trappfamilyfarm.com` to `news@trappfamilyfarm.com`, nothing in the code consumes it, so no newsletter is generated.

In short, the mismatch arises because you attempted to trigger the newsletter loop by sending an email directly.  The implemented logic requires using the portal’s newsletter‑admin interface; it does not listen for incoming mail to `news@…` as a trigger.


## Conclusion: I want to align the workflow to work as I described, their should not be a separate tool for newsletter. There should only be the mediation view of newsletter type profile JSON's that allow for a selection of the user that can send newsletters.


## Test email newsletter with the incorrect workflow, but correct usage of the unsubscribe:
```eml
Delivered-To: dylancarsonmontgomery@gmail.com
Received: by 2002:a05:7108:78c1:b0:54e:2939:8558 with SMTP id h1csp1259561gdu;
        Sun, 5 Apr 2026 22:44:12 -0700 (PDT)
X-Received: by 2002:a05:622a:1386:b0:50d:835f:3407 with SMTP id d75a77b69052e-50d835f7869mr78956821cf.45.1775454252282;
        Sun, 05 Apr 2026 22:44:12 -0700 (PDT)
ARC-Seal: i=1; a=rsa-sha256; t=1775454252; cv=none;
        d=google.com; s=arc-20240605;
        b=JyWUHSFcbtpGTK4xoV9l5mwPUdEVYHeBpGnE4mzcxydtm8o63hOgHb1Zxg8cTX+DWl
         QctXmp83osDBtFZ/Z2O2dIUOlBA6346C0EfYWxv07CEjz8jMZT++dYf4pb+pYuxQkHKL
         rrwkUVQQwO1kpPSjp15sV/baXxS6pQJ9xLdor7WCjlkS7jOmcD/eVRu/OkoD2yJ8riZ+
         GrWIS8U/0ziy5uAw9b4EAW0DOL6Vjms6+ykb1p2sofrJglNuVYgqZEDR2Ednmf9CxZyT
         xFCKQ4w2hbjG2sqVfpc9j+JklV5OI5hrI/Bbj9y3nf6NDpRg3uQTPdrNIRrVVukBPGzW
         WctA==
ARC-Message-Signature: i=1; a=rsa-sha256; c=relaxed/relaxed; d=google.com; s=arc-20240605;
        h=feedback-id:date:message-id:mime-version:subject:to:reply-to:from
         :dkim-signature:dkim-signature;
        bh=eeYXdHSYwPv4QJusb/fagT+PA9lk97kLmbr4sQz5840=;
        fh=VirLth2DJFhuptnsr0HtNEkrMIMQYe9F5L+bLc93Ktk=;
        b=F2zdnvu1tzIuajuowXOofxGvk54cGPcDSTTRNqvqqIpGgQDZcvLnodkKyiQt4xsLvx
         y8hogsbKGWnpHHlcgAjIrZX0rHY7VBbF4VcE1K1Q/xxlPJYP3lBchqEhuhV+xx5jaooy
         2HqfURK61tE1N5oBhsi09hV4NpI6p+HazQzleMAGtJ/VCTb54HHFkGLbi9ZaLWfmlDfY
         NYe/sAAMyXRUWSq1j2g522ZVgwoYBQSzJ2YGe6xTSXouOwn+DmtRjKqqKwB/GUlv731d
         SAt57jWJEJg0Didf3V4GZ/zKUMyQdkMjN9oxyVvHCIdxjKDh90YgzoJHYO2HFna9lJob
         IgGA==;
        dara=google.com
ARC-Authentication-Results: i=1; mx.google.com;
       dkim=pass header.i=@cuyahogavalleycountrysideconservancy.org header.s=34hmf5cgogheom62v6msoxsbnn2f3mbs header.b=TgllNpEQ;
       dkim=pass header.i=@amazonses.com header.s=224i4yxa5dv7c2xz3womw6peuasteono header.b=LxjDeK7p;
       spf=pass (google.com: domain of 0100019d6151e9e5-9b062341-4459-4727-b3e6-712f72aa0ca3-000000@amazonses.com designates 54.240.8.237 as permitted sender) smtp.mailfrom=0100019d6151e9e5-9b062341-4459-4727-b3e6-712f72aa0ca3-000000@amazonses.com
Return-Path: <0100019d6151e9e5-9b062341-4459-4727-b3e6-712f72aa0ca3-000000@amazonses.com>
Received: from a8-237.smtp-out.amazonses.com (a8-237.smtp-out.amazonses.com. [54.240.8.237])
        by mx.google.com with ESMTPS id d75a77b69052e-50d4b867a99si175965741cf.167.2026.04.05.22.44.11
        for <dylancarsonmontgomery@gmail.com>
        (version=TLS1_3 cipher=TLS_AES_128_GCM_SHA256 bits=128/128);
        Sun, 05 Apr 2026 22:44:12 -0700 (PDT)
Received-SPF: pass (google.com: domain of 0100019d6151e9e5-9b062341-4459-4727-b3e6-712f72aa0ca3-000000@amazonses.com designates 54.240.8.237 as permitted sender) client-ip=54.240.8.237;
Authentication-Results: mx.google.com;
       dkim=pass header.i=@cuyahogavalleycountrysideconservancy.org header.s=34hmf5cgogheom62v6msoxsbnn2f3mbs header.b=TgllNpEQ;
       dkim=pass header.i=@amazonses.com header.s=224i4yxa5dv7c2xz3womw6peuasteono header.b=LxjDeK7p;
       spf=pass (google.com: domain of 0100019d6151e9e5-9b062341-4459-4727-b3e6-712f72aa0ca3-000000@amazonses.com designates 54.240.8.237 as permitted sender) smtp.mailfrom=0100019d6151e9e5-9b062341-4459-4727-b3e6-712f72aa0ca3-000000@amazonses.com
DKIM-Signature: v=1; a=rsa-sha256; q=dns/txt; c=relaxed/simple;
	s=34hmf5cgogheom62v6msoxsbnn2f3mbs;
	d=cuyahogavalleycountrysideconservancy.org; t=1775454251;
	h=From:Reply-To:To:Subject:MIME-Version:Content-Type:Message-ID:Date;
	bh=eeYXdHSYwPv4QJusb/fagT+PA9lk97kLmbr4sQz5840=;
	b=TgllNpEQEW93AM2hjTD4rvwcb/WEn+vUil+fv/fcK3fUIhdL86/0/3gi12i6IJBB
	VFnHHsY0aFCCsLEkQwnY5pFjKw7U+nUrPx/GFueVrob8aeNtsc/p90EwW7H4R98VUHm
	X19UmdIwf+fMYmfm7oGPT6EQRfly0n7ahEKQauXFjy8w9BLIt5hSSHKoTO1mX5Aywlb
	g+fkJSVZNcTiZdH4NOt6cHvtwFPeN6UVKJQySKi0RvDfnpBPmbVxGiuJewOVqRVtQey
	dVT+WKReSn36v+WmvI9oZzaFDRLs6ATH1bXFWlU45p6IVsHRxl9nxamwfylMCJYPKQx
	GYv8BRmhfw==
DKIM-Signature: v=1; a=rsa-sha256; q=dns/txt; c=relaxed/simple;
	s=224i4yxa5dv7c2xz3womw6peuasteono; d=amazonses.com; t=1775454251;
	h=From:Reply-To:To:Subject:MIME-Version:Content-Type:Message-ID:Date:Feedback-ID;
	bh=eeYXdHSYwPv4QJusb/fagT+PA9lk97kLmbr4sQz5840=;
	b=LxjDeK7pSz94IuTGkSH80tWjhdnt6kWYX7b/orkfJXHSP0opiQ39kTUqQVB3XXEK
	EWYZ970qoLZc47CH6/rnp10rfbIcj7ON2vbznM8L0MjRvYAHOIoXl9AuqLukoPcMX3f
	ofhxgHcGlkyAj/rwPeliiMs8GlSyiB48SknqhMHE=
From: technicalContact@cuyahogavalleycountrysideconservancy.org
Reply-To: news@cuyahogavalleycountrysideconservancy.org
To: dylancarsonmontgomery@gmail.com
Subject: CVCC live newsletter loop test
MIME-Version: 1.0
Content-Type: multipart/alternative; 
	boundary="----=_Part_317227_1153938910.1775454251493"
Message-ID: <0100019d6151e9e5-9b062341-4459-4727-b3e6-712f72aa0ca3-000000@email.amazonses.com>
Date: Mon, 6 Apr 2026 05:44:11 +0000
Feedback-ID: ::1.us-east-1.I1P7YGAwgniWgQZ0WgsQzbXlB/KcjXm4hEWr+Ii/oqU=:AmazonSES
X-SES-Outgoing: 2026.04.06-54.240.8.237

------=_Part_317227_1153938910.1775454251493
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 7bit

This is a live end-to-end newsletter loop test from the new newsletter-admin service tool.

Unsubscribe: https://cuyahogavalleycountrysideconservancy.org/__fnd/newsletter/unsubscribe?email=dylancarsonmontgomery@gmail.com&token=93293b72cc9d584fcf628d1fa08df127e16f186bbadddb356f5ebe02016b3165

------=_Part_317227_1153938910.1775454251493
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: 7bit

<p>This is a live end-to-end newsletter loop test from the new newsletter-admin service tool.</p><hr><p style="font-size:0.95rem;color:#47524b">If you no longer want these updates, <a href="https://cuyahogavalleycountrysideconservancy.org/__fnd/newsletter/unsubscribe?email=dylancarsonmontgomery@gmail.com&amp;token=93293b72cc9d584fcf628d1fa08df127e16f186bbadddb356f5ebe02016b3165">unsubscribe here</a>.</p>
------=_Part_317227_1153938910.1775454251493--
```