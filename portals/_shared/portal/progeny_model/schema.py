from __future__ import annotations

from typing import Any, TypedDict


class MemberStatus(TypedDict):
    state: str
    updated_unix_ms: int


class MemberDisplay(TypedDict):
    title: str


class MemberCapabilities(TypedDict):
    paypal: bool
    aws: bool


class MemberProfileRefs(TypedDict):
    paypal_profile_id: str
    paypal_site_base_url: str
    paypal_checkout_return_url: str
    paypal_checkout_cancel_url: str
    paypal_webhook_listener_url: str
    paypal_checkout_brand_name: str
    aws_profile_id: str
    aws_emailer_list_ref: str
    aws_emailer_entry_ref: str
    keycloak_realm_ref: str
    keycloak_client_ref: str


class MemberContractRefs(TypedDict):
    authorization_contract_id: str
    service_agreement_ref: str


class MemberProfile(TypedDict):
    schema: str
    member_id: str
    member_msn_id: str
    display: MemberDisplay
    capabilities: MemberCapabilities
    profile_refs: MemberProfileRefs
    contract_refs: MemberContractRefs
    status: MemberStatus
    legacy: dict[str, Any]
