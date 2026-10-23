"""Planner errors (A§4.8). `NO_LODGING` is a warning, never an exception ([D-2])."""


class PlannerError(Exception):
    code: str = "PLANNER_ERROR"


class InvalidInput(PlannerError):
    code = "INVALID_INPUT"

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


class Unreachable(PlannerError):
    code = "UNREACHABLE"

    def __init__(self, point_index: int, snap_km: float | None = None) -> None:
        super().__init__(f"point {point_index} unreachable (snap {snap_km} km)")
        self.point_index = point_index
        self.snap_km = snap_km


class TooShort(PlannerError):
    code = "TOO_SHORT"

    def __init__(self, road_km: float) -> None:
        super().__init__(f"road distance {road_km:.1f} km is too short")
        self.road_km = road_km


class UpstreamUnavailable(PlannerError):
    code = "UPSTREAM"

    def __init__(self, service: str) -> None:
        super().__init__(f"upstream {service} unavailable")
        self.service = service


class NotFound(PlannerError):
    code = "NOT_FOUND"

    def __init__(self, entity: str, id: str) -> None:
        super().__init__(f"{entity} {id} not found")
        self.entity = entity
        self.id = id


class PlanCancelled(PlannerError):
    code = "CANCELLED"

    def __init__(self) -> None:
        super().__init__("plan cancelled")


class OpeningHoursParseError(ValueError):
    """Unsupported `opening_hours` syntax; the place is excluded and logged (A§6.3)."""
