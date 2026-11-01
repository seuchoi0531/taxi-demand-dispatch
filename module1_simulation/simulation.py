"""Command-driven taxi/passenger runtime, independent of Panda3D and policies."""

from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import math

from .city import City, fields, identifier, node, number, tick_at
from .configuration import SimulationConfig


class SimulationClock:
    def __init__(self, tick_seconds: float) -> None:
        number(tick_seconds, "tick_seconds", positive=True)
        self._tick_seconds = tick_seconds
        self._tick = 0

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def time_seconds(self) -> float:
        return self._tick * self._tick_seconds

    def advance(self, ticks: int = 1) -> None:
        if type(ticks) is not int or ticks < 0:
            raise ValueError("ticks: expected a non-negative integer")
        self._tick += ticks

    def reset(self) -> None:
        self._tick = 0


@dataclass(frozen=True)
class _Request:
    call_id: str
    origin: tuple[int, int]
    destination: tuple[int, int]
    requested_at_seconds: float
    tick: int


@dataclass
class Passenger:
    """One released request and its runtime lifecycle. Never shared by reference."""

    call_id: str
    origin: tuple[int, int]
    destination: tuple[int, int]
    requested_at_seconds: float
    state: str = "waiting"
    taxi_id: str | None = None
    assigned_at_seconds: float | None = None
    picked_up_at_seconds: float | None = None
    completed_at_seconds: float | None = None


@dataclass
class _Taxi:
    taxi_id: str
    speed_mps: float
    current_node: tuple[int, int]
    x_m: float
    y_m: float
    state: str = "idle"
    call_id: str | None = None
    heading_degrees: float = 0
    route: deque = field(default_factory=deque)
    distance_m: float = 0
    empty_distance_m: float = 0
    completed_calls: int = 0
    times: dict = field(default_factory=lambda: dict.fromkeys(
        ("idle_seconds", "pickup_seconds", "occupied_seconds"), 0.0))


@dataclass(frozen=True)
class TaxiSnapshot:
    taxi_id: str
    x_m: float
    y_m: float
    heading_degrees: float
    distance_m: float
    state: str
    call_id: str | None
    zone_id: str


@dataclass(frozen=True)
class PassengerSnapshot:
    call_id: str
    origin: tuple[int, int]
    destination: tuple[int, int]
    requested_at_seconds: float
    state: str
    taxi_id: str | None
    assigned_at_seconds: float | None
    picked_up_at_seconds: float | None
    completed_at_seconds: float | None
    x_m: float
    y_m: float
    wait_seconds: float


class Simulation:
    """Execute explicit commands. No matching, forecasting or random call generation."""

    def __init__(self, config: SimulationConfig, calls=()) -> None:
        self.config = config
        self.city = City(config.block_size_m)
        self._initial_requests = self._parse_calls(calls)
        self.reset()

    @property
    def has_initial_calls(self) -> bool:
        return bool(self._initial_requests)

    def _parse_calls(self, calls) -> list[_Request]:
        requests = []
        ids = set()
        for item in calls:
            fields(item, {"call_id", "origin", "destination", "requested_at_seconds"}, "call")
            call_id = item["call_id"]
            identifier(call_id, "call_id")
            if call_id in ids:
                raise ValueError(f"duplicate call_id: {call_id}")
            ids.add(call_id)
            tick = tick_at(item["requested_at_seconds"], self.config.tick_seconds, call_id)
            requests.append(_Request(
                call_id, node(item["origin"], f"{call_id}.origin"),
                node(item["destination"], f"{call_id}.destination"),
                item["requested_at_seconds"], tick))
        return sorted(requests, key=lambda r: (r.tick, r.call_id))

    def add_calls(self, calls) -> None:
        """Ingest existing scenario records atomically; never generate demand here."""
        requests = self._parse_calls(calls)
        known_ids = {r.call_id for r in self._requests}
        for request in requests:
            if request.call_id in known_ids:
                raise ValueError(f"duplicate call_id: {request.call_id}")
            if request.tick < self.tick:
                raise ValueError(f"{request.call_id}: cannot add a call in the past")
        released = self._requests[:self._cursor]
        pending = sorted(self._requests[self._cursor:] + requests, key=lambda r: (r.tick, r.call_id))
        self._requests = released + pending
        self._release_calls()

    @property
    def tick(self) -> int:
        return self._clock.tick

    @property
    def time_seconds(self) -> float:
        return self._clock.time_seconds

    def reset(self) -> None:
        self._requests = list(self._initial_requests)
        self._clock = SimulationClock(self.config.tick_seconds)
        self._taxis = {}
        for taxi in sorted(self.config.taxis, key=lambda t: t.taxi_id):
            x, y = taxi.initial_node
            self._taxis[taxi.taxi_id] = _Taxi(taxi.taxi_id, taxi.speed_mps, taxi.initial_node,
                                              x * self.config.block_size_m,
                                              y * self.config.block_size_m)
        self._passengers = {}
        self._events = []
        self._cursor = 0
        self._record("simulation_started", 0)
        self._release_calls()

    def _record(self, event, time, taxi_id=None, call_id=None, **details) -> None:
        self._events.append(dict(time_seconds=time, event=event, taxi_id=taxi_id,
                                 call_id=call_id, details=details))

    def _release_calls(self) -> None:
        while self._cursor < len(self._requests):
            request = self._requests[self._cursor]
            if request.tick > self.tick:
                break
            self._cursor += 1
            self._passengers[request.call_id] = Passenger(
                request.call_id, request.origin, request.destination, request.requested_at_seconds)
            self._record("call_created", self.time_seconds, call_id=request.call_id,
                         origin=list(request.origin), destination=list(request.destination))

    def advance(self, ticks: int = 1) -> None:
        if type(ticks) is not int or ticks < 0:
            raise ValueError("ticks: expected a non-negative integer")
        for _ in range(ticks):
            for taxi in self._taxis.values():
                self._move(taxi, self.config.tick_seconds, self.time_seconds)
            self._clock.advance()
            self._release_calls()

    def dispatch(self, taxi_id: str, call_id: str) -> None:
        self.apply_command(dict(type="dispatch", taxi_id=taxi_id, call_id=call_id))

    def apply_command(self, command: dict) -> None:
        try:
            if not isinstance(command, dict):
                raise ValueError("command: expected a dict")
            kind = command.get("type")
            if kind != "dispatch":
                raise ValueError(f"unknown command type: {kind!r}")
            fields(command, {"type", "taxi_id", "call_id"}, "command")
            identifier(command["taxi_id"], "taxi_id")
            identifier(command["call_id"], "call_id")
            taxi = self._taxis.get(command["taxi_id"])
            if taxi is None:
                raise ValueError(f"unknown taxi_id: {command['taxi_id']}")
            if taxi.state != "idle":
                raise ValueError(f"{taxi.taxi_id}: taxi must be idle, is {taxi.state}")
            passenger = self._passengers.get(command["call_id"])
            if passenger is None:
                raise ValueError(f"call not available: {command['call_id']}")
            if passenger.state != "waiting":
                raise ValueError(f"{passenger.call_id}: call must be waiting, is {passenger.state}")
            taxi.call_id, taxi.state = passenger.call_id, "to_pickup"
            passenger.state, passenger.taxi_id = "assigned", taxi.taxi_id
            passenger.assigned_at_seconds = self.time_seconds
            taxi.route = deque(self.city.shortest_path(taxi.current_node, passenger.origin))
            self._record("assigned", self.time_seconds, taxi.taxi_id, passenger.call_id)
            self._settle(taxi, self.time_seconds)
        except ValueError as exc:
            supplied = command if isinstance(command, dict) else {}
            self._record("command_rejected", self.time_seconds,
                         taxi_id=supplied.get("taxi_id") if isinstance(supplied.get("taxi_id"), str) else None,
                         call_id=supplied.get("call_id") if isinstance(supplied.get("call_id"), str) else None,
                         reason=str(exc))
            raise

    def _settle(self, taxi: _Taxi, time: float) -> None:
        # Preserve true sub-tick arrivals, but remove arithmetic noise at boundaries.
        step = self.config.tick_seconds
        boundary = round(time / step) * step
        if math.isclose(time, boundary, rel_tol=0, abs_tol=min(1e-9, step * 1e-7)):
            time = boundary
        while not taxi.route and taxi.state != "idle":
            if taxi.state == "to_pickup":
                passenger = self._passengers[taxi.call_id]
                if passenger.state != "assigned" or passenger.taxi_id != taxi.taxi_id:
                    raise RuntimeError(f"inconsistent pickup: {taxi.taxi_id}/{taxi.call_id}")
                passenger.state, passenger.picked_up_at_seconds = "onboard", time
                taxi.state = "occupied"
                self._record("pickup_completed", time, taxi.taxi_id, passenger.call_id)
                self._record("trip_started", time, taxi.taxi_id, passenger.call_id)
                taxi.route = deque(self.city.shortest_path(taxi.current_node, passenger.destination))
            elif taxi.state == "occupied":
                passenger = self._passengers[taxi.call_id]
                if passenger.state != "onboard" or passenger.taxi_id != taxi.taxi_id:
                    raise RuntimeError(f"inconsistent dropoff: {taxi.taxi_id}/{taxi.call_id}")
                passenger.state, passenger.completed_at_seconds = "completed", time
                self._record("dropoff_completed", time, taxi.taxi_id, passenger.call_id)
                taxi.call_id, taxi.state = None, "idle"
                taxi.completed_calls += 1
            else:
                raise RuntimeError(f"invalid taxi state: {taxi.state}")

    def _move(self, taxi: _Taxi, budget: float, start: float) -> None:
        elapsed = 0.0
        time_fields = {"to_pickup": "pickup_seconds", "occupied": "occupied_seconds"}
        while budget > 0:
            if taxi.state == "idle":
                taxi.times["idle_seconds"] += budget
                return
            if not taxi.route:
                raise RuntimeError(f"moving taxi without route: {taxi.taxi_id}")
            end = taxi.route[0]
            x, y = (n * self.config.block_size_m for n in end)
            dx, dy = x - taxi.x_m, y - taxi.y_m
            distance = math.hypot(dx, dy)
            needed = distance / taxi.speed_mps
            arrived = needed <= budget + 1e-12
            duration = min(needed, budget) if arrived else budget
            travel = distance if arrived else duration * taxi.speed_mps
            taxi.times[time_fields[taxi.state]] += duration
            taxi.distance_m += travel
            if taxi.state != "occupied":
                taxi.empty_distance_m += travel
            taxi.heading_degrees = math.degrees(math.atan2(-dx, dy))
            elapsed += duration
            budget = max(0.0, budget - duration)
            if arrived:
                taxi.x_m, taxi.y_m = x, y
                taxi.current_node = end
                taxi.route.popleft()
                self._settle(taxi, start + elapsed)
            else:
                taxi.x_m += dx * travel / distance
                taxi.y_m += dy * travel / distance

    def snapshot(self) -> tuple[TaxiSnapshot, ...]:
        return tuple(TaxiSnapshot(t.taxi_id, t.x_m, t.y_m, t.heading_degrees,
                                  t.distance_m, t.state, t.call_id,
                                  self.city.zone_at(t.x_m, t.y_m)) for t in self._taxis.values())

    def passenger_snapshots(self) -> tuple[PassengerSnapshot, ...]:
        result = []
        for passenger in self._passengers.values():
            if passenger.state == "onboard":
                taxi = self._taxis[passenger.taxi_id]
                x, y = taxi.x_m, taxi.y_m
            else:
                point = passenger.destination if passenger.state == "completed" else passenger.origin
                x, y = (v * self.config.block_size_m for v in point)
            until = passenger.picked_up_at_seconds
            wait = (self.time_seconds if until is None else until) - passenger.requested_at_seconds
            if wait < -1e-9:
                raise RuntimeError(f"negative passenger wait: {passenger.call_id}")
            result.append(PassengerSnapshot(**asdict(passenger), x_m=x, y_m=y,
                                             wait_seconds=max(0.0, wait)))
        return tuple(result)

    def metrics(self) -> dict:
        by_taxi = {t.taxi_id: dict(**t.times, distance_m=t.distance_m,
                                   empty_distance_m=t.empty_distance_m,
                                   completed_calls=t.completed_calls) for t in self._taxis.values()}
        picked = [p.picked_up_at_seconds - p.requested_at_seconds
                  for p in self._passengers.values() if p.picked_up_at_seconds is not None]
        completed = sum(p.state == "completed" for p in self._passengers.values())
        available = self.time_seconds * len(self._taxis)
        return dict(by_taxi=by_taxi, fleet_available_seconds=available,
                    completed_calls=completed, pending_calls=len(self._passengers) - completed,
                    picked_up_calls=len(picked), mean_wait_seconds=sum(picked) / len(picked) if picked else None,
                    occupancy_percent=(100 * sum(t.times["occupied_seconds"] for t in self._taxis.values())
                                       / available) if available else None,
                    rejected_commands=sum(e["event"] == "command_rejected" for e in self._events))

    def observe(self) -> dict:
        passengers = []
        for passenger in self.passenger_snapshots():
            data = asdict(passenger)
            data["origin"], data["destination"] = list(data["origin"]), list(data["destination"])
            passengers.append(data)
        return dict(schema_version="0.1", tick=self.tick, time_seconds=self.time_seconds,
                    taxis=[asdict(t) for t in self.snapshot()], passengers=passengers, metrics=self.metrics())

    def events(self) -> list[dict]:
        return deepcopy(sorted(self._events, key=lambda e: e["time_seconds"]))
