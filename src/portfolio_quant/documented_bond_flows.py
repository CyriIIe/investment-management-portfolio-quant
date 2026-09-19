"""Validation documentaire hors ligne des flux obligataires unitaires.

Aucun prix, accès CORE, accès réseau ou calcul de performance ici.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from portfolio_quant.deterministic_total_return import BondFlow


SUPPORTED_TYPES = {
    "FIXED_KNOWN",
    "DISCOUNT_NO_COUPON",
    "FIXED_AMORTIZING",
}


@dataclass(frozen=True)
class DocumentedBondFlows:
    isin: str
    secid: str
    coupon_type: str
    valuation_date: date
    maturity_date: date
    observation_date: date
    currency: str
    primary_board: str
    face_value: Decimal
    flows: tuple[BondFlow, ...]
    coupon_count: int
    principal_event_count: int
    historical_availability_proven: bool = False


def decimal_value(value, field: str) -> Decimal:
    if value is None or isinstance(value, (float, bool)):
        raise ValueError(f"{field}: montant absent ou invalide")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field}: montant invalide") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{field}: montant non positif ou non fini")
    return number


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_documented_bond_flows(document: dict) -> DocumentedBondFlows:
    """Valide un calendrier documenté ; ne certifie pas un historique sans biais."""
    require(isinstance(document, dict), "Document non JSON objet")

    instrument = document["instrument"]
    market = document["market_reference"]
    completeness = document["completeness"]
    coupons = document["cashflows"]
    principal_events = document["principal_events"]

    require(isinstance(instrument, dict), "Instrument invalide")
    require(isinstance(market, dict), "Référence marché invalide")
    require(isinstance(completeness, dict), "Complétude invalide")
    require(isinstance(coupons, list), "Coupons invalides")
    require(isinstance(principal_events, list), "Principal invalide")

    valuation = date.fromisoformat(document["valuation_date"])
    maturity = date.fromisoformat(instrument["maturity_date"])
    observed = date.fromisoformat(instrument["source_observation_date"])
    coupon_type = instrument["coupon_type"]
    currency = instrument["currency"]
    board = instrument["primary_board"]
    face = decimal_value(instrument["face_value"], "nominal")

    require(coupon_type in SUPPORTED_TYPES, "Type d'obligation non pris en charge")
    require(instrument["status"] == "VERIFIED", "Instrument non vérifié")
    require(currency == "RUB", "Devise non prise en charge")
    require(isinstance(board, str) and bool(board), "Board primaire absent")
    require(valuation < maturity, "Échéance antérieure à la valorisation")
    require(observed >= valuation, "Observation documentaire incohérente")

    require(market["status"] == "VERIFIED", "Prix de référence non vérifié")
    require(market["trade_date"] == document["valuation_date"],
            "Date de marché incohérente")
    require(market["board"] == board, "Board de marché incohérent")
    require(market["canonical_close_price_field"] == "LEGALCLOSEPRICE",
            "Champ de clôture non conforme")
    require(market["accrued_interest_field"] == "ACCINT",
            "Champ d'intérêts courus non conforme")

    require(not document["conditional_events"],
            "Événement conditionnel : examen manuel nécessaire")
    require(completeness["coupon_schedule_complete"] is True,
            "Calendrier des coupons incomplet")
    require(completeness["principal_schedule_complete"] is True,
            "Calendrier du principal incomplet")
    require(completeness["face_value_reconciled"] is True,
            "Nominal déclaré non réconcilié")
    require(completeness["usable_for_deterministic_simulation"] is True,
            "Document non éligible")
    require(
        completeness["as_of_2026_09_10_schedule_publication_proven"] is False,
        "Statut historique inattendu : réexaminer la provenance",
    )

    if coupon_type == "DISCOUNT_NO_COUPON":
        require(not coupons and instrument["coupon_frequency_per_year"] == 0,
                "Zéro coupon non confirmé")
        require(completeness["coupon_count_post_valuation_date"] == 0,
                "Nombre de coupons incohérent")
    else:
        require(bool(coupons), "Coupons fixes absents")

    require(completeness["coupon_count_post_valuation_date"] == len(coupons),
            "Nombre de coupons différent du document")

    flows = []
    seen = set()

    def add_event(event: dict, expected_kind: str) -> Decimal:
        require(isinstance(event, dict), "Événement invalide")
        payment = date.fromisoformat(event["date"])
        amount = decimal_value(event["amount"], "flux")

        require(
            event["status"] == "VERIFIED"
            and event["currency"] == currency
            and valuation < payment <= maturity,
            "Flux non vérifié, hors période ou mauvaise devise",
        )
        require(
            event["availability_status"] == "UNKNOWN"
            and event["available_on_or_before_2026_09_10"] is None
            and event["source_observation_date"] == observed.isoformat(),
            "Provenance temporelle non conforme",
        )

        identity = (payment, expected_kind)
        require(identity not in seen, "Flux de même type et date dupliqué")
        seen.add(identity)
        flows.append(BondFlow(payment, expected_kind, amount))
        return amount

    for event in coupons:
        require(event["type"] == "COUPON", "Coupon de type inattendu")
        add_event(event, "COUPON")

    principal_sum = Decimal("0")
    amortization_count = 0
    for event in principal_events:
        require(
            event["type"] in {"AMORTIZATION", "MATURITY_REDEMPTION"},
            "Type de remboursement non pris en charge",
        )
        if event["type"] == "AMORTIZATION":
            amortization_count += 1
        else:
            require(date.fromisoformat(event["date"]) == maturity,
                    "Remboursement final hors échéance")

        principal_sum += add_event(event, "PRINCIPAL")

    require(principal_sum == face, "Somme du principal différente du nominal")
    require(
        decimal_value(completeness["principal_amount_total"],
                      "principal déclaré") == principal_sum,
        "Principal déclaré différent du calendrier",
    )
    require(bool(principal_events), "Aucun remboursement")
    require(
        (coupon_type == "FIXED_AMORTIZING") == (amortization_count > 0),
        "Classification amortissable incohérente",
    )
    require(
        completeness["amortizations_present_before_maturity"]
        is (any(
            event["type"] == "AMORTIZATION"
            and date.fromisoformat(event["date"]) < maturity
            for event in principal_events
        )),
        "Indicateur d'amortissement incohérent",
    )

    return DocumentedBondFlows(
        isin=instrument["isin"],
        secid=instrument["secid"],
        coupon_type=coupon_type,
        valuation_date=valuation,
        maturity_date=maturity,
        observation_date=observed,
        currency=currency,
        primary_board=board,
        face_value=face,
        flows=tuple(sorted(flows, key=lambda flow: (
            flow.payment_date, flow.kind
        ))),
        coupon_count=len(coupons),
        principal_event_count=len(principal_events),
        historical_availability_proven=False,
    )


def build_bond_case(
    document: DocumentedBondFlows,
    *,
    horizon_date: date,
    verified_dirty_price: Decimal,
):
    """Prépare un calcul unitaire avec prix dirty vérifié par l'appelant.

    Cette fonction ne vérifie PAS elle-même le prix contre CORE ou MOEX.
    Elle ne doit pas être utilisée pour publier un résultat de marché sans
    un rapprochement de prix distinct.
    """
    from portfolio_quant.deterministic_total_return import BondCase

    require(
        isinstance(document, DocumentedBondFlows),
        "Calendrier documentaire non validé",
    )
    require(
        isinstance(horizon_date, date)
        and document.valuation_date < horizon_date < document.maturity_date,
        "Horizon hors de la période obligataire",
    )

    price = decimal_value(verified_dirty_price, "prix dirty")
    zero_coupon = document.coupon_type == "DISCOUNT_NO_COUPON"

    return BondCase(
        valuation_date=document.valuation_date,
        horizon_date=horizon_date,
        currency=document.currency,
        dirty_price=price,
        remaining_principal=document.face_value,
        flows=document.flows,
        fixed_coupon_verified=not zero_coupon,
        complete_schedule_verified=True,
        primary_board_verified=True,
        zero_coupon_verified=zero_coupon,
    )
