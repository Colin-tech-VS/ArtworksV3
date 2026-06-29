"""Modèle économique Artworks V3 — abonnements + commission ventes (aligné V2 staging)."""
from __future__ import annotations


def commission_rate() -> float:
    from .pricing_store import get_commission_rate
    return get_commission_rate()


def commission_percent_label() -> str:
    from .pricing_store import commission_percent_label as _label
    return _label()


def seller_net_cents(gross_cents: int) -> int:
    return int(round(gross_cents * (1 - commission_rate())))


def seller_net_label(gross_cents: int) -> str:
    net = seller_net_cents(gross_cents) / 100
    if net == int(net):
        return f'{int(net)} €'
    return f'{net:.2f} €'.replace('.', ',')


def commission_cents(gross_cents: int) -> int:
    return int(round(gross_cents * commission_rate()))
