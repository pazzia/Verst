"""Real car routing over a self-hosted GraphHopper server (ADR-0017). Stdlib only, behind `RoutingPort`.

Not wired into any composition root yet: the app and the goldens keep `HybridRouting` / `FakeRouting` until
ENG-04 (ADR-0017 §5). Server side: `GraphHopperRouting.from_env(os.environ)` with `VERST_GRAPHHOPPER_URL`.
"""

from verst_planner.adapters.graphhopper.mapping import DETAILS, MappingError, normalize_ref, to_route
from verst_planner.adapters.graphhopper.routing import (
    ENV_TIMEOUT,
    ENV_URL,
    GraphHopperRouting,
    GraphHopperSettings,
    request_body,
)
from verst_planner.adapters.graphhopper.transport import Transport, TransportError, UrllibTransport

__all__ = [
    "DETAILS",
    "ENV_TIMEOUT",
    "ENV_URL",
    "GraphHopperRouting",
    "GraphHopperSettings",
    "MappingError",
    "Transport",
    "TransportError",
    "UrllibTransport",
    "normalize_ref",
    "request_body",
    "to_route",
]
