"""Panda3D view of the prototype. Simulation code never imports this module."""

import math
from pathlib import Path

from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight, AntialiasAttrib, ClockObject, DirectionalLight, Geom, GeomNode,
    GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
    NodePath, TextNode, Vec4, WindowProperties,
)

from .demo import DemoRunner


def _unit_box() -> NodePath:
    """Create a lit cube without downloading external models or textures."""
    data = GeomVertexData("box", GeomVertexFormat.getV3n3(), Geom.UHStatic)
    vertices = GeomVertexWriter(data, "vertex")
    normals = GeomVertexWriter(data, "normal")
    triangles = GeomTriangles(Geom.UHStatic)
    faces = (
        ((0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
        ((0, 0, -1), ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1))),
        ((1, 0, 0), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1))),
        ((-1, 0, 0), ((-1, 1, -1), (-1, -1, -1), (-1, -1, 1), (-1, 1, 1))),
        ((0, 1, 0), ((1, 1, -1), (-1, 1, -1), (-1, 1, 1), (1, 1, 1))),
        ((0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
    )
    for face, (normal, corners) in enumerate(faces):
        for corner in corners:
            vertices.addData3(*(v / 2 for v in corner))
            normals.addData3(*normal)
        offset = face * 4
        triangles.addVertices(offset, offset + 1, offset + 2)
        triangles.addVertices(offset, offset + 2, offset + 3)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode("box")
    node.addGeom(geom)
    return NodePath(node)


class CityApp(ShowBase):
    def __init__(self, runner: DemoRunner, *, window_type: str = "onscreen") -> None:
        super().__init__(windowType=window_type)
        self.disableMouse()
        self.runner = runner
        self.simulation = runner.simulation
        self._selected_taxi = 0
        self._selected_call = 0
        self._message = ""
        self.paused = False
        self.playback_speed = 1.0
        self._accumulator = 0.0
        self._angle = -55.0
        self._elevation = 55.0
        self._radius = 158.0
        self._cube = _unit_box()
        self.setBackgroundColor(1, 1, 1)
        self.render.setAntialias(AntialiasAttrib.MAuto)
        if window_type == "onscreen" and self.win is not None:
            props = WindowProperties()
            props.setTitle("Taxi Digital Twin | Module 1")
            props.setSize(1200, 800)
            self.win.requestProperties(props)
        self.camLens.setNearFar(0.1, 1000)
        self.camLens.setFov(48)
        self._lights()
        self._city()
        self.taxi_nodes = {taxi.taxi_id: self._taxi(taxi.taxi_id, i)
                           for i, taxi in enumerate(self.simulation.snapshot())}
        self.passenger_nodes = {}
        self.show_details = False
        self._build_hud()
        self.accept("space", self.toggle_pause)
        self.accept("r", self.reset_simulation)
        self.accept("d", self.toggle_details)
        self.accept("t", self.cycle_selection, ["taxi"])
        self.accept("c", self.cycle_selection, ["call"])
        self.accept("enter", self.manual_dispatch)
        self.accept("escape", self.userExit)
        for key, speed in (("1", 0.5), ("2", 1.0), ("3", 2.0)):
            self.accept(key, self.set_speed, [speed])
        for key, angle, elevation in (("arrow_left", -8, 0), ("arrow_right", 8, 0),
                                      ("arrow_up", 0, 5), ("arrow_down", 0, -5)):
            self.accept(key, self.orbit, [angle, elevation])
            self.accept(key + "-repeat", self.orbit, [angle, elevation])
        self.accept("wheel_up", self.zoom, [-8])
        self.accept("wheel_down", self.zoom, [8])
        self.orbit(0, 0)
        self.refresh()
        self.taskMgr.add(self._update, "simulation-tick")

    def _build_hud(self) -> None:
        # Use a local system font when available; keep Panda's font as fallback.
        self._font = None
        for source in ("/System/Library/Fonts/Supplemental/Arial.ttf",
                       "C:/Windows/Fonts/arial.ttf",
                       "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if Path(source).is_file():
                self._font = self.loader.loadFont(source)
                self._font.setPixelsPerUnit(80)
                break

        def text(value, parent, x, y, size=0.032, color=(0.42, 0.46, 0.5, 1),
                 align=TextNode.ALeft, change=False):
            kwargs = {"font": self._font} if self._font is not None else {}
            return OnscreenText(text=value, parent=parent, pos=(x, y), scale=size,
                                fg=color, align=align, mayChange=change, **kwargs)

        text("M O B I L I T Y   L A B", self.a2dTopLeft, 0.09, -0.09, 0.025)
        text("City simulation", self.a2dTopLeft, 0.09, -0.18, 0.062,
             (0.12, 0.15, 0.18, 1))
        text("3 x 3 blocks   /   3 taxis", self.a2dTopLeft, 0.09, -0.24)
        self._hud = text("", self.a2dTopRight, -0.09, -0.13, 0.04,
                         (0.12, 0.15, 0.18, 1), TextNode.ARight, True)
        self._playback = text("", self.a2dTopRight, -0.09, -0.20,
                              align=TextNode.ARight, change=True)
        self._summary = text("", self.a2dTopRight, -0.09, -0.29, 0.029,
                             align=TextNode.ARight, change=True)
        self._wait_summary = text("", self.a2dTopRight, -0.09, -0.35, 0.027,
                                  align=TextNode.ARight, change=True)
        self._fleet_rows = []
        self._coordinate_rows = []
        for index in range(3):
            y = -0.42 - index * 0.18
            DirectFrame(parent=self.a2dTopLeft, pos=(0.09, 0, y + 0.012),
                        frameSize=(0, 0.008, -0.025, 0.025),
                        frameColor=(0.93, 0.71, 0.19, 1))
            self._fleet_rows.append(text("", self.a2dTopLeft, 0.12, y, 0.033,
                                         (0.24, 0.28, 0.32, 1), change=True))
            self._coordinate_rows.append(text("", self.a2dTopLeft, 0.12, y - 0.055,
                                              0.026, change=True))
        mode = "Auto demo / nearest available taxi" if self.runner.auto_assign else "Manual / waiting for commands"
        self._mode_text = text(mode,
                               self.a2dTopLeft, 0.09, -0.93, 0.027)
        self._selection = text("", self.a2dTopLeft, 0.09, -1.04, 0.026, change=True)
        self._notice = text("", self.a2dBottomLeft, 0.09, 0.22, 0.027,
                            (0.65, 0.28, 0.18, 1), change=True)
        text("SPACE  Play / pause     R  Reset     1 / 2 / 3  Speed",
             self.a2dBottomLeft, 0.09, 0.14, 0.027)
        text("Arrows  Orbit     Scroll  Zoom     D  Coordinates     Esc  Exit",
             self.a2dBottomLeft, 0.09, 0.09, 0.027)

    def toggle_details(self) -> None:
        self.show_details = not self.show_details
        self.refresh()

    def cycle_selection(self, target: str) -> None:
        if target == "taxi":
            self._selected_taxi = (self._selected_taxi + 1) % 3
        elif target == "call":
            self._selected_call += 1
        self.refresh()

    def manual_dispatch(self) -> None:
        if self.runner.auto_assign:
            self._message = "Manual controls: restart with --manual."
        else:
            taxi = self.simulation.snapshot()[self._selected_taxi]
            try:
                calls = [p for p in self.simulation.passenger_snapshots() if p.state == "waiting"]
                if not calls:
                    raise ValueError("No waiting calls to assign.")
                call = calls[self._selected_call % len(calls)]
                self.simulation.dispatch(taxi.taxi_id, call.call_id)
                self._message = "Command accepted."
            except ValueError as exc:
                self._message = str(exc)
        self.refresh()

    def _box(self, parent, position, scale, color):
        node = self._cube.copyTo(parent)
        node.setPos(*position)
        node.setScale(*scale)
        node.setColor(*color)
        return node

    def _lights(self) -> None:
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.75, 0.75, 0.75, 1))
        self.render.setLight(self.render.attachNewNode(ambient))
        sunlight = DirectionalLight("sunlight")
        sunlight.setColor(Vec4(0.3, 0.3, 0.3, 1))
        light = self.render.attachNewNode(sunlight)
        light.setHpr(-30, -60, 0)
        self.render.setLight(light)

    def _city(self) -> None:
        size = self.simulation.config.block_size_m
        extent = size * 3
        road = size * 0.22
        city = self.render.attachNewNode("city")
        self._box(city, (extent / 2, extent / 2, -0.5),
                  (extent + road + 4, extent + road + 4, 1), (0.91, 0.93, 0.92, 1))
        for i in range(4):
            coordinate = i * size
            for position, scale in (
                ((coordinate, extent / 2, 0.03), (road, extent + road, 0.1)),
                ((extent / 2, coordinate, 0.03), (extent + road, road, 0.1)),
            ):
                self._box(city, position, scale, (0.77, 0.8, 0.82, 1))
            for j in range(3):
                for fraction in (0.3, 0.5, 0.7):
                    along = (j + fraction) * size
                    self._box(city, (coordinate, along, 0.1),
                              (0.12, size * 0.08, 0.025), (1, 1, 1, 1))
                    self._box(city, (along, coordinate, 0.1),
                              (size * 0.08, 0.12, 0.025), (1, 1, 1, 1))
        for row in range(3):
            for col in range(3):
                x, y = (col + 0.5) * size, (row + 0.5) * size
                self._box(city, (x, y, 0.15), (size - road - 1, size - road - 1, 0.3),
                          (0.93, 0.95, 0.93, 1))
                for bx, by, height in ((-0.18, -0.15, 4), (0.18, 0.18, 6)):
                    height += (row + col) % 3
                    self._box(city, (x + size * bx, y + size * by, height / 2 + 0.3),
                              (size * 0.23, size * 0.28, height),
                              (0.78 + col * 0.025, 0.84 + row * 0.02, 0.86, 1))

    def _taxi(self, taxi_id: str, index: int):
        root = self.render.attachNewNode(taxi_id)
        self._box(root, (0, 0, 0.65), (1.6, 3.2, 0.65), (1, 0.72, 0.12, 1))
        self._box(root, (0, -0.2, 1.2), (1.4, 1.6, 0.65), (0.12, 0.25, 0.35, 1))
        self._box(root, (0, -0.2, 1.58), (1.45, 1.65, 0.12), (1, 0.79, 0.22, 1))
        for x in (-0.85, 0.85):
            for y in (-1.0, 1.0):
                self._box(root, (x, y, 0.4), (0.25, 0.65, 0.65), (0.04, 0.05, 0.07, 1))
        self._box(root, (0, 1.63, 0.7), (1.3, 0.08, 0.25), (1, 1, 0.8, 1))
        beacon = self._box(root, (0, -0.2, 1.8), (0.8, 0.45, 0.35), (1, 0.88, 0.45, 1))
        beacon.setName("status-beacon")
        label = TextNode(f"label-{taxi_id}")
        label.setText(f"{index + 1:02d}")
        label.setAlign(TextNode.ACenter)
        label.setTextColor(0.18, 0.22, 0.26, 1)
        label_node = root.attachNewNode(label)
        label_node.setPos(0, 0, 3.0)
        label_node.setScale(1.2)
        label_node.setBillboardPointEye()
        label_node.setLightOff()
        label_node.setColor(1, 1, 1, 1)
        return root

    def _passenger(self, call_id: str):
        root = self.render.attachNewNode(f"passenger-{call_id}")
        self._box(root, (0, 0, 0.9), (0.65, 0.45, 1.05), (0.2, 0.5, 0.9, 1))
        self._box(root, (0, 0, 1.7), (0.5, 0.5, 0.5), (0.95, 0.76, 0.58, 1))
        for x in (-0.19, 0.19):
            self._box(root, (x, 0, 0.25), (0.23, 0.3, 0.5), (0.22, 0.27, 0.33, 1))
        label = TextNode(f"label-{call_id}")
        label.setText(call_id)
        label.setAlign(TextNode.ACenter)
        label.setTextColor(0.12, 0.3, 0.5, 1)
        label_node = root.attachNewNode(label)
        label_node.setPos(0, 0, 2.7)
        label_node.setScale(0.9)
        label_node.setBillboardPointEye()
        label_node.setLightOff()
        return root

    def _sync_passengers(self, passengers) -> None:
        visible = {
            p.call_id: p for p in passengers
            if p.state in ("waiting", "assigned") or (
                p.state == "completed"
                and self.simulation.time_seconds - p.completed_at_seconds < 3)
        }
        for call_id in self.passenger_nodes.keys() - visible.keys():
            self.passenger_nodes.pop(call_id).removeNode()
        for call_id, passenger in visible.items():
            if call_id not in self.passenger_nodes:
                self.passenger_nodes[call_id] = self._passenger(call_id)
            model = self.passenger_nodes[call_id]
            # Stand beside the road; this offset is presentation only.
            model.setPos(passenger.x_m + 1.2, passenger.y_m + 1.2, 0.1)
            if passenger.state == "completed":
                model.setColorScale(0.75, 1, 0.8, 1)
            else:
                model.clearColorScale()

    def orbit(self, angle: float, elevation: float) -> None:
        self._angle += angle
        self._elevation = min(80, max(25, self._elevation + elevation))
        center = self.simulation.config.block_size_m * 1.5
        a, e = math.radians(self._angle), math.radians(self._elevation)
        self.camera.setPos(center + self._radius * math.cos(e) * math.cos(a),
                           center + self._radius * math.cos(e) * math.sin(a),
                           self._radius * math.sin(e))
        self.camera.lookAt(center, center, 0)

    def zoom(self, change: float) -> None:
        self._radius = min(200, max(55, self._radius + change))
        self.orbit(0, 0)

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.refresh()

    def set_speed(self, speed: float) -> None:
        self.playback_speed = speed
        self.refresh()

    def reset_simulation(self) -> None:
        self.runner.reset()
        self._message = ""
        self._selected_call = 0
        self._accumulator = 0.0
        self.refresh()

    def refresh(self) -> None:
        taxis = self.simulation.snapshot()
        passengers = self.simulation.passenger_snapshots()
        colors = {"idle": (1, 0.82, 0.3, 1), "to_pickup": (0.25, 0.55, 1, 1),
                  "occupied": (0.22, 0.75, 0.48, 1)}
        for taxi in taxis:
            node = self.taxi_nodes[taxi.taxi_id]
            node.setPos(taxi.x_m, taxi.y_m, 0.1)
            node.setH(taxi.heading_degrees)
            node.find("**/status-beacon").setColor(*colors[taxi.state])
        self._sync_passengers(passengers)
        self._hud.setText(f"Simulation time   {self.simulation.time_seconds:05.1f} s")
        self._playback.setText(
            f"{'Paused' if self.paused else 'Playing'}   /   {self.playback_speed:g}x speed")
        waiting = sum(p.state in ("waiting", "assigned") for p in passengers)
        onboard = sum(p.state == "onboard" for p in passengers)
        metrics = self.simulation.metrics()
        self._summary.setText(f"Waiting {waiting}   /   Onboard {onboard}   /   Completed {metrics['completed_calls']}")
        wait = metrics["mean_wait_seconds"]
        self._wait_summary.setText("Mean pickup wait   " + (f"{wait:.1f} s" if wait is not None else "-"))
        states = {"idle": "Waiting", "to_pickup": "Picking up", "occupied": "With passenger"}
        for index, taxi in enumerate(taxis):
            self._fleet_rows[index].setText(f"Taxi {index + 1:02d}    {states[taxi.state]}")
            self._coordinate_rows[index].setText(
                f"x {taxi.x_m:.1f} m   /   y {taxi.y_m:.1f} m" if self.show_details
                else (taxi.call_id or ""))
        self._notice.setText(self._message)
        if not self.runner.auto_assign:
            waiting_calls = [p for p in passengers if p.state == "waiting"]
            call = waiting_calls[self._selected_call % len(waiting_calls)].call_id if waiting_calls else "none"
            self._selection.setText(
                f"T  Taxi {self._selected_taxi + 1:02d}\nC  Call: {call}\nEnter  Assign")

    def _update(self, task):
        if not self.paused:
            self._accumulator += ClockObject.getGlobalClock().getDt() * self.playback_speed
            step = self.simulation.config.tick_seconds
            ticks = int(self._accumulator / step)
            if ticks:
                try:
                    self.runner.advance(ticks)
                except ValueError as exc:
                    self.paused = True
                    self._message = f"Simulation stopped: {exc}"
                self._accumulator -= ticks * step
                self.refresh()
        return task.cont
