"""Deterministic explanations of observed portfolio changes; no I/O."""

from dataclasses import dataclass

from portfolio_quant.portfolio_changes import PortfolioChanges


@dataclass(frozen=True)
class ChangeExplanations:
    previous_date: str
    current_date: str
    observations: tuple[str, ...]
    limitations: tuple[str, ...]
    performance_measure: bool = False
    portfolio_risk_measure: bool = False


def explain_changes(changes: PortfolioChanges) -> ChangeExplanations:
    """Explain observations without inventing their financial causes."""
    if not isinstance(changes, PortfolioChanges):
        raise ValueError("Expected validated portfolio changes")

    observations = []

    if changes.added_count:
        observations.append(
            f"{changes.added_count} position(s) apparue(s) parmi les "
            "positions actives. La cause de cette apparition n'est "
            "pas établie par les photographies seules."
        )

    if changes.removed_count:
        observations.append(
            f"{changes.removed_count} position(s) disparue(s) parmi les "
            "positions actives. Une disparition ne prouve pas une vente."
        )

    if changes.quantity_changed_count:
        observations.append(
            f"{changes.quantity_changed_count} position(s) présente(s) "
            "aux deux dates ont changé de quantité. Les transactions "
            "doivent être examinées pour en déterminer la cause."
        )

    if changes.value_changed_at_constant_quantity_count:
        observations.append(
            f"{changes.value_changed_at_constant_quantity_count} "
            "position(s) ont changé de valeur observée à quantité "
            "constante. Cela ne mesure pas la performance."
        )

    if changes.accrued_changed_at_constant_quantity_count:
        observations.append(
            f"{changes.accrued_changed_at_constant_quantity_count} "
            "position(s) ont changé d'intérêts courus à quantité "
            "constante. Il faut vérifier les dates et les conditions "
            "des coupons pour interpréter ces variations."
        )

    if changes.source_only_changed_count:
        observations.append(
            f"{changes.source_only_changed_count} position(s) ont "
            "uniquement changé d'identifiant d'observation parmi "
            "les champs comparés. Aucun changement économique "
            "n'est établi par ce seul constat."
        )

    if changes.unchanged_count:
        observations.append(
            f"{changes.unchanged_count} position(s) ne présentent "
            "aucun changement dans les champs comparés."
        )

    if not observations:
        observations.append(
            "Aucun changement détecté dans les champs comparés."
        )

    return ChangeExplanations(
        previous_date=changes.previous_date,
        current_date=changes.current_date,
        observations=tuple(observations),
        limitations=(
            "Les catégories de variation de valeur et d'intérêts "
            "courus peuvent se chevaucher.",
            "Les photographies seules ne prouvent ni achat, ni vente, "
            "ni gain ou perte.",
            "Cette comparaison ne constitue pas une mesure du "
            "risque global du portefeuille.",
        ),
    )
