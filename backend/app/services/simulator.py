from dataclasses import dataclass


@dataclass(frozen=True)
class SimulatedCreateOutcome:
    accepted: bool
    persisted_quantity: int
    reported_quantity: int


def simulate_create_purchase_order(
    *,
    mode: str,
    requested_quantity: int,
    case_pack_quantity: int,
) -> SimulatedCreateOutcome:
    persisted_quantity = requested_quantity
    if mode == "persist_short":
        persisted_quantity = max(
            case_pack_quantity,
            requested_quantity - case_pack_quantity,
        )

    return SimulatedCreateOutcome(
        accepted=True,
        persisted_quantity=persisted_quantity,
        reported_quantity=requested_quantity,
    )
