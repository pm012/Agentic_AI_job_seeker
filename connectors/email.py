"""
ImapReceiver implements port MessageReceiver: gets unread letters from the agent mailbox
using IMAP and returns typed IncomingMessage. 
The agent’s second "hand" is also a passive I/O component: it only reads data and makes no decisions.

For demonstration purposes, a `MockReceiver` (which also implements `MessageReceiver`) 
returns a pre-configured response—a fallback used if IMAP is unavailable or the mailbox is empty. 
Switching the adapter requires changing just a single line of code; the core logic and the agent’s main loop remain untouched 
(following the "ports and adapters" pattern).

To perform a live demonstration, send an email from any email account to `AGENT_EMAIL`. The `ImapReceiver` will then read it 
(note that the email must be unread, and IMAP must be enabled in the Gmail settings).
"""

import email as emaillib
import imaplib
import os
import smtplib
from email.header import decode_header, make_header
from email.message import Message
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from core.models import Attachment, IncomingMessage
from core.ports import MessageReceiver, MessageSender


def _decode_header(value: str) -> str:
    """MIME encoded-word head (=?UTF-8?B?...?=) -> regular row.

    Gmail encodes not-ASCII themes and names as per RFC 2047 (=?UTF-8?B?...?=). 
    Without encoding in  subject/sender raw "=?UTF-8?B?...?=" strings 
    appear—spoiling both the visual appearance
    and the input for LLMs. `make_header(decode_header())` assembles these parts into readable text.
    """
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _extract_plain_text(msg: Message) -> str:
    """GET text/plain from the letter (multipart or simple)."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", "replace")


class ImapReceiver:
    """MessageReceiver via Gmail IMAP."""

    HOST = "imap.gmail.com"

    def fetch_unread(self, limit: int = 5) -> list[IncomingMessage]:
        out: list[IncomingMessage] = []
        # App Password у .env sometimes with whitespaces (format 'xxxx xxxx xxxx xxxx').
        pwd = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
        with imaplib.IMAP4_SSL(self.HOST) as m:
            m.login(os.environ["AGENT_EMAIL"], pwd)
            m.select("INBOX")
            _, ids = m.search(None, "UNSEEN")
            for num in ids[0].split()[:limit]:
                _, data = m.fetch(num, "(RFC822)")
                msg = emaillib.message_from_bytes(data[0][1])
                out.append(
                    IncomingMessage(
                        sender=_decode_header(msg["From"] or ""),
                        subject=_decode_header(msg["Subject"] or ""),
                        body=_extract_plain_text(msg),
                    )
                )
        return out


# Prepared response of "employer" for demo feedback: contains als it immediately includes both a range
# (closing the gap) and a time proposal — this will be needed for the "interview" branch
_DEFAULT_REPLY = IncomingMessage(
    sender="HR Techery <hr@techery.example>",
    subject="Re: відгук на Senior Python Engineer",
    body=(
        "Доброго дня! Дякуємо за відгук — профіль цікавий, і ваш AI-агент вразив. "
        "Зарплатна вилка для позиції — $5000–7000. "
        "Чи зручно вам онлайн-співбесіда у четвер о 15:00?"
    ),
)


class MockReceiver:
    """Fallback-MessageReceiver: returns prepared response without network"""

    def __init__(self, messages: list[IncomingMessage] | None = None) -> None:
        self._messages = messages if messages is not None else [_DEFAULT_REPLY]

    def fetch_unread(self, limit: int = 5) -> list[IncomingMessage]:
        return self._messages[:limit]


class GmailSender:
    """MessageSender via Gmail SMTP — for correspondence (replying to employers). 

`dry_run=True` by default (mock mode): sends nothing, simply prints the email. 
Actual sending — `dry_run=False` (SMTP to `AGENT_EMAIL` using an App Password).
    """

    HOST = "smtp.gmail.com"
    PORT = 587

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: list[Attachment] | None = None,
    ) -> None:
        sender = os.environ["AGENT_EMAIL"]
        to_addr = parseaddr(to)[1] or to  # 'HR <hr@x>' -> 'hr@x'

        if self.dry_run:
            print("🧪 [DRY-RUN] the letter was NOT sent  (mock). It would have been sent:")
            print(f"   From: {sender}  →  To: {to_addr}")
            print(f"   Subject: {subject}")
            print(f"   {body[:160]}{'…' if len(body) > 160 else ''}")
            return

        msg = MIMEMultipart()
        msg["From"], msg["To"], msg["Subject"] = sender, to_addr, subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        for att in attachments or []:
            with open(att.path, "rb") as f:
                part = MIMEApplication(f.read())
            part.add_header("Content-Disposition", "attachment", filename=att.filename)
            msg.attach(part)

        pwd = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
        with smtplib.SMTP(self.HOST, self.PORT) as s:
            s.starttls()
            s.login(sender, pwd)
            s.send_message(msg)
        print(f"✅ The letter was sent to {to_addr}")


_check_imap: MessageReceiver = ImapReceiver()  # static check of the contract
_check_mock: MessageReceiver = MockReceiver()
_check_gmail: MessageSender = GmailSender()