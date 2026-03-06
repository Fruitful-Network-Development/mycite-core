from __future__ import annotations

from typing import Any, TypedDict


class ServiceNavItem(TypedDict):
    service_id: str
    label: str
    href: str
    active: bool


class NetworkTabItem(TypedDict):
    tab_id: str
    label: str
    href: str
    active: bool


class CardDisplay(TypedDict, total=False):
    title: str
    subtitle: str


class CardContact(TypedDict, total=False):
    name: str
    email: str


class CardStatus(TypedDict, total=False):
    state: str
    note: str


class CardSource(TypedDict, total=False):
    kind: str
    ref: str
    path: str
    exists: bool


class ProfileCard(TypedDict, total=False):
    schema: str
    progeny_id: str
    msn_id: str
    progeny_type: str
    display: CardDisplay
    contact: CardContact
    alias_expected: bool
    status: CardStatus
    source: CardSource
    raw: dict[str, Any]
