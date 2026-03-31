"""
AMARA OS — Offer Sender + Follow-Up System

Generates offer letters from queued OfferRecords, schedules follow-ups,
and tracks response status.

This module does NOT send emails directly — it generates the message
content and creates a scheduled follow-up queue. The caller (orchestrator
or CLI) is responsible for the actual send mechanism.

All generated offers are logged to the vault.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from system.offer_queue import OfferRecord, get_queue
from system.vault import read_vault_file, write_vault_file, list_vault
from system.config import SFR_TARGET_ASSIGNMENT_FEE, DEAL_STATUS_OFFER_SENT


# ─── Offer Message ────────────────────────────────────────────────────────────

@dataclass
class OfferMessage:
    message_id:     str
    offer_id:       str
    address:        str
    zip_code:       str
    buyer_name:     str
    asset_type:     str          # SFR / land
    subject:        str
    body:           str
    channel:        str = "email"   # email / sms / letter
    status:         str = "draft"   # draft / sent / delivered / replied / expired
    created_at:     str = field(default_factory=lambda: date.today().isoformat())
    sent_at:        str = ""
    replied_at:     str = ""
    reply_summary:  str = ""

    def preview(self) -> str:
        return (
            f"[{self.status.upper()}] {self.message_id} — {self.address}\n"
            f"  To: {self.buyer_name} | Channel: {self.channel}\n"
            f"  Subject: {self.subject}\n"
            f"  Body ({len(self.body)} chars)"
        )


# ─── Follow-Up Schedule ───────────────────────────────────────────────────────

@dataclass
class FollowUpSchedule:
    offer_id:       str
    address:        str
    buyer_name:     str
    followups:      list[tuple[date, int, str]]  # (send_date, attempt_number, template_key)

    def summary(self) -> str:
        lines = [f"Follow-Up Schedule — {self.address} (offer {self.offer_id})"]
        for send_date, attempt, tmpl in self.followups:
            lines.append(f"  Attempt {attempt}: {send_date.isoformat()} [{tmpl}]")
        return "\n".join(lines)


# ─── Templates ────────────────────────────────────────────────────────────────

SFR_OFFER_TEMPLATE = """\
Hi {seller_name},

I'm reaching out about your property at {address}.

We're real estate investors who buy properties in {zip_code} and we're \
interested in making you a cash offer.

Our offer: **${offer_price:,.0f} cash** — as-is, no repairs, no commissions.

We can close in as little as {close_days} days and handle all the paperwork. \
No fees, no hassle.

If you're open to a conversation, I'd love to connect — even if our offer \
doesn't work, there's no pressure.

Call or reply to this message anytime.

{sender_name}
"""

LAND_OFFER_TEMPLATE = """\
Hi {seller_name},

I came across your land at {address} and wanted to reach out directly.

We work with builders and developers in {zip_code} and are actively \
looking for land in this area.

Our offer: **${offer_price:,.0f} cash** for the {acres:.1f} acres — \
all cash, no contingencies.

We can move quickly and close on your timeline.

If you'd like to discuss, I'm available at your convenience.

{sender_name}
"""

FOLLOWUP_1_TEMPLATE = """\
Hi {seller_name},

Just following up on my message from {days_ago} days ago about {address}.

Our cash offer of **${offer_price:,.0f}** is still available. \
We're flexible on timing and can work around your schedule.

If you have any questions or want to talk through the details, \
please don't hesitate to reach out.

{sender_name}
"""

FOLLOWUP_2_TEMPLATE = """\
Hi {seller_name},

Last check-in on {address} — we're still interested and the offer stands.

I know timing isn't always right, so if you ever reconsider in the future, \
please keep us in mind. We're buyers in {zip_code} long-term.

No pressure — just wanted to leave the door open.

{sender_name}
"""

TEMPLATES = {
    "sfr_offer":   SFR_OFFER_TEMPLATE,
    "land_offer":  LAND_OFFER_TEMPLATE,
    "followup_1":  FOLLOWUP_1_TEMPLATE,
    "followup_2":  FOLLOWUP_2_TEMPLATE,
}


# ─── In-Memory Store ──────────────────────────────────────────────────────────

_messages:   list[OfferMessage]      = []
_schedules:  list[FollowUpSchedule]  = []


# ─── Generate Offer Message ───────────────────────────────────────────────────

def generate_offer_message(
    offer:        OfferRecord,
    seller_name:  str = "Property Owner",
    sender_name:  str = "AMARA Acquisitions",
    acres:        float = 0.0,
    close_days:   int = 14,
    channel:      str = "email",
) -> OfferMessage:
    """
    Generate a personalized offer message from an approved OfferRecord.
    """
    msg_id = f"MSG-{uuid.uuid4().hex[:6].upper()}"

    is_land     = offer.asset_type.upper() != "SFR"
    template_key = "land_offer" if is_land else "sfr_offer"
    template     = TEMPLATES[template_key]

    # Use MAO as the offer price presented to seller
    # (this is NOT the wholesale assignment fee — it's what we offer the seller)
    offer_price = offer.max_offer

    if is_land:
        body = template.format(
            seller_name  = seller_name,
            address      = offer.address,
            zip_code     = offer.zip_code,
            offer_price  = offer_price,
            acres        = acres if acres > 0 else 1.0,
            sender_name  = sender_name,
        )
        subject = f"Cash Offer — {offer.address} ({offer.zip_code})"
    else:
        body = template.format(
            seller_name  = seller_name,
            address      = offer.address,
            zip_code     = offer.zip_code,
            offer_price  = offer_price,
            close_days   = close_days,
            sender_name  = sender_name,
        )
        subject = f"Cash Offer — {offer.address}"

    msg = OfferMessage(
        message_id   = msg_id,
        offer_id     = offer.offer_id,
        address      = offer.address,
        zip_code     = offer.zip_code,
        buyer_name   = offer.primary_buyer_name,
        asset_type   = offer.asset_type,
        subject      = subject,
        body         = body,
        channel      = channel,
    )

    _messages.append(msg)
    _log_offer_to_vault(offer, msg)
    return msg


def generate_followup_message(
    offer:        OfferRecord,
    attempt:      int,
    seller_name:  str = "Property Owner",
    sender_name:  str = "AMARA Acquisitions",
    days_ago:     int = 7,
) -> OfferMessage:
    """Generate a follow-up message for an offer."""
    msg_id       = f"MSG-{uuid.uuid4().hex[:6].upper()}"
    template_key = f"followup_{min(attempt, 2)}"
    template     = TEMPLATES.get(template_key, FOLLOWUP_2_TEMPLATE)

    body = template.format(
        seller_name = seller_name,
        address     = offer.address,
        zip_code    = offer.zip_code,
        offer_price = offer.max_offer,
        days_ago    = days_ago,
        sender_name = sender_name,
    )
    subject = f"Following Up — {offer.address} Cash Offer (#{attempt})"

    msg = OfferMessage(
        message_id  = msg_id,
        offer_id    = offer.offer_id,
        address     = offer.address,
        zip_code    = offer.zip_code,
        buyer_name  = offer.primary_buyer_name,
        asset_type  = offer.asset_type,
        subject     = subject,
        body        = body,
        channel     = "email",
    )
    _messages.append(msg)
    return msg


# ─── Follow-Up Scheduler ─────────────────────────────────────────────────────

def schedule_followups(
    offer:      OfferRecord,
    send_date:  date | None = None,
    intervals:  list[int] = None,   # days after initial send for each follow-up
) -> FollowUpSchedule:
    """
    Build a follow-up schedule for an offer.

    Default schedule:
    - Day 0:  Initial offer
    - Day 7:  Follow-up #1
    - Day 14: Follow-up #2
    """
    send_date = send_date or date.today()
    intervals = intervals or [7, 14]

    followups = []
    for i, offset in enumerate(intervals, 1):
        fu_date = send_date + timedelta(days=offset)
        template = f"followup_{min(i, 2)}"
        followups.append((fu_date, i, template))

    schedule = FollowUpSchedule(
        offer_id   = offer.offer_id,
        address    = offer.address,
        buyer_name = offer.primary_buyer_name,
        followups  = followups,
    )
    _schedules.append(schedule)
    return schedule


# ─── Due Follow-Ups ───────────────────────────────────────────────────────────

@dataclass
class DueFollowUp:
    offer_id:    str
    address:     str
    buyer_name:  str
    attempt:     int
    due_date:    date
    template:    str


def get_due_followups(today: date | None = None) -> list[DueFollowUp]:
    """Return all follow-ups due today or earlier."""
    today = today or date.today()

    # Track which offers have received replies — skip those
    replied_offers = {m.offer_id for m in _messages if m.replied_at}

    due = []
    for sched in _schedules:
        if sched.offer_id in replied_offers:
            continue
        for fu_date, attempt, template in sched.followups:
            if fu_date <= today:
                due.append(DueFollowUp(
                    offer_id   = sched.offer_id,
                    address    = sched.address,
                    buyer_name = sched.buyer_name,
                    attempt    = attempt,
                    due_date   = fu_date,
                    template   = template,
                ))

    due.sort(key=lambda x: x.due_date)
    return due


# ─── Mark Replied ─────────────────────────────────────────────────────────────

def record_reply(
    offer_id:      str,
    reply_summary: str,
    replied_at:    str | None = None,
) -> None:
    """
    Record a seller reply for an offer.
    Marks all messages for this offer as replied and cancels pending follow-ups.
    """
    today = replied_at or date.today().isoformat()
    for msg in _messages:
        if msg.offer_id == offer_id and msg.status in ("sent", "draft"):
            msg.replied_at   = today
            msg.reply_summary = reply_summary
            msg.status       = "replied"

    # Remove pending follow-up schedule
    global _schedules
    _schedules = [s for s in _schedules if s.offer_id != offer_id]


# ─── Mark Sent ───────────────────────────────────────────────────────────────

def mark_sent(message_id: str, sent_at: str | None = None) -> None:
    sent_at = sent_at or date.today().isoformat()
    for msg in _messages:
        if msg.message_id == message_id:
            msg.status  = "sent"
            msg.sent_at = sent_at
            return


# ─── Vault Logging ────────────────────────────────────────────────────────────

def _log_offer_to_vault(offer: OfferRecord, msg: OfferMessage) -> None:
    """
    Write an offer message record to the vault under offers/.
    Creates the offers/ directory entry for tracking.
    """
    today    = date.today().isoformat()
    filename = f"{offer.offer_id}_{msg.message_id}.md"
    slug     = "".join(c if c.isalnum() else "_" for c in offer.address)[:30]

    content  = f"# Offer — {offer.address}\n\n"
    content += f"## Offer ID\n{offer.offer_id}\n\n"
    content += f"## Message ID\n{msg.message_id}\n\n"
    content += f"## Status\n{msg.status}\n\n"
    content += f"## Buyer Match\n{offer.primary_buyer_id} — {offer.primary_buyer_name}\n\n"
    content += f"## Offer Price\n${offer.max_offer:,.0f}\n\n"
    content += f"## Subject\n{msg.subject}\n\n"
    content += f"## Body\n{msg.body}\n\n"
    content += f"## Timeline\n"
    content += f"- **Queued:** {offer.queued_at[:10]}\n"
    content += f"- **Generated:** {today}\n"
    content += f"- **Sent:** \n"
    content += f"- **Reply Received:** \n\n"
    content += f"## Reply Notes\n\n"
    content += f"## Outcome\n"
    content += f"- **Deal ID:** {offer.vault_deal_id or 'pending'}\n"
    content += f"- **Final Status:** \n"

    write_vault_file("offers", filename, content)


# ─── Batch Offer Generation ───────────────────────────────────────────────────

def process_offer_queue(
    sender_name: str = "AMARA Acquisitions",
    channel:     str = "email",
) -> list[OfferMessage]:
    """
    Generate offer messages for all pending offers in the queue.
    Returns list of generated messages ready to review and send.
    """
    pending = get_queue(status="pending")
    messages = []
    for offer in pending:
        msg = generate_offer_message(
            offer       = offer,
            sender_name = sender_name,
            channel     = channel,
        )
        schedule_followups(offer)
        messages.append(msg)

    return messages


def print_offer_queue_report(messages: list[OfferMessage]) -> None:
    print(f"\n{'═' * 60}")
    print(f"OFFER QUEUE — {len(messages)} messages generated")
    print(f"{'─' * 60}")
    for msg in messages:
        print(f"  {msg.preview()}")
    print(f"{'═' * 60}\n")
