"""
DouFormSender — send vacancy reply via DOU form.

Implements port MessageSender (core/ports.py). It's «silent» I/O: that doesn't deside 
when adn where to send, doesn't asks confirmation - it just calls helper. Solution «wether
to act» takes agent, permission should be given by human (approval gate in jupiter notebook). 
"""

import os

from core.models import Attachment
from core.ports import MessageSender
from helpers import dou_helper


class DouFormSender:
    """MessageSender для відгуку на DOU. Тонкий адаптер над dou_helper."""

    def __init__(self, dry_run: bool = True) -> None:
        # dry_run=True (МОК) за замовчуванням — безпечно; реальний відгук = False.
        self.dry_run = dry_run

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: list[Attachment] | None = None,
    ) -> None:
        # 'to' - vacancy URL  (apply_url).
        # 'subject' ignored as DOU form has only text(descr).
        # attachments: take the frist file as CV (user_cv), if it is present.
        cv_path = attachments[0].path if attachments else None
        dou_helper.apply_for_vacancy(
            url=to,
            message=body,
            sessionid=os.environ["DOU_SESSIONID"],
            csrftoken=os.environ["DOU_CSRFTOKEN"],
            cv_path=cv_path,
            dry_run=self.dry_run,
        )


# Create and instance and assign it to the variable with port type. 
# Same implementation in email.py, vacancy_source.py, gcal.py because google calendar needs OAuth during instance creation

_check: MessageSender = DouFormSender()