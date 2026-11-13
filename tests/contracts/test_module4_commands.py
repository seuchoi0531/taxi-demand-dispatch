from module4_dispatch import build_plan
from module1_simulation import Simulation, load_config

from tests.module4.test_policy import BLOCK_SIZE_M, forecasts, observation, passenger, taxi


def test_dispatch_command_remains_executable_by_module1():
    state = observation(
        taxis=[taxi("taxi-1", (0, 0))],
        passengers=[passenger("call-1", (0, 0), 0)],
        time_seconds=0,
    )
    state["tick"] = 0
    state["passengers"][0]["wait_seconds"] = 0
    plan = build_plan(state, block_size_m=BLOCK_SIZE_M)
    command = plan["commands"][0]

    simulation = Simulation(
        load_config("configs/module1_demo.toml"),
        [{"call_id": "call-1", "origin": [0, 0], "destination": [1, 1], "requested_at_seconds": 0}],
    )
    simulation.apply_command(command)
    assert simulation.observe()["passengers"][0]["state"] == "onboard"


def test_reposition_command_matches_module1_execution_contract():
    state = observation(taxis=[taxi("taxi-a", (0, 0)), taxi("taxi-b", (0, 0))])
    plan = build_plan(
        state,
        block_size_m=BLOCK_SIZE_M,
        forecasts=forecasts({"zone-2-2": 1.0}),
    )
    command = plan["commands"][0]

    assert command == {"type": "reposition", "taxi_id": "taxi-a", "destination": [2, 2]}
    assert set(command) == {"type", "taxi_id", "destination"}


def test_generated_reposition_runs_without_conversion():
    simulation = Simulation(load_config("configs/module1_demo.toml"))
    plan = build_plan(simulation.observe(), block_size_m=simulation.config.block_size_m,
                      forecasts=forecasts({"zone-0-2": 1}, prediction_time=0))
    for command in plan["commands"]:
        simulation.apply_command(command)
    assert any(t["state"] == "repositioning" and t["call_id"] is None
               for t in simulation.observe()["taxis"])
    simulation.advance(400)
    assert all(t["state"] == "idle" for t in simulation.observe()["taxis"])
    assert any(e["event"] == "reposition_completed" and e["details"]["destination"] == [0, 2]
               for e in simulation.events())
