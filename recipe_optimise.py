#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["networkx", "ortools"]
# ///

import json
import logging

from argparse import ArgumentParser, FileType
from collections import deque
from dataclasses import dataclass, field
from typing import Iterator

import networkx as nx
from ortools.sat.python import cp_model

logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())


@dataclass(kw_only=True)
class Step:
    id: str
    duration: int
    parents: list[str] = field(default_factory=list)
    hands_off: bool = False
    prepable: bool = False
    instruction: str | None = None


@dataclass
class Recipe:
    steps: list[Step]

    @classmethod
    def from_json(cls, data):
        return cls(steps=[Step(**i) for i in data["steps"]])


@dataclass
class Offset:
    offset: int
    step: Step


@dataclass
class OffsetMap:
    offsets: list[Offset]

    def __post_init__(self):
        self._map: dict[str, Offset] = {x.step.id: x for x in self.offsets}
        self._graph = to_graph([x.step for x in self.offsets])

    def get_steps(self, pos: int) -> list[Step]:
        return [
            x.step for x in self.offsets if x.offset <= pos < x.offset + x.step.duration
        ]

    def get_moves(self, steps: list[Step]) -> tuple[list[Step], int]:
        if not (possible_sticks := [s for s in steps if not s.prepable]):
            possible_sticks = steps

        stick = min(possible_sticks, key=lambda s: s.duration + self._map[s.id].offset)

        return [s for s in steps if s != stick], stick.duration + self._map[
            stick.id
        ].offset

    def move_after(self, step: Step, target: int) -> bool:
        distance = target - self._map[step.id].offset
        return self.move(step, distance)

    def move(self, step: Step, distance: int) -> bool:
        """
        :returns: True if children were moved and we need to backtrack
        """
        # a step may be the parent of multiple steps
        # but only want to move it once
        seen: set[str] = set()
        backtrack = False
        to_move = deque([step.id])

        while to_move:
            sid = to_move.pop()

            if sid in seen:
                continue

            seen.add(sid)

            off = self._map[sid]
            off.offset += distance

            to_move.extendleft(off.step.parents)
            # if not off.step.prepable:
            #     backtrack = True
            #     to_move.extendleft(self._graph.successors(sid))

        return backtrack

    def total_time(self) -> int:
        return max(x.offset + x.step.duration for x in self.offsets)

    def reverse(self) -> "OffsetMap":
        total = self.total_time()
        return OffsetMap(
            [Offset(total - x.offset - x.step.duration, x.step) for x in self.offsets]
        )


def to_graph(steps: list[Step]) -> nx.DiGraph:
    g = nx.DiGraph()
    for s in steps:
        g.add_node(s.id)  # keep steps with no parents or children
        for p in s.parents:
            g.add_edge(p, s.id)
    return g


def get_conflicts(steps: list[Step]) -> list[Step] | None:
    hands_on = [s for s in steps if not s.hands_off]
    return None if len(hands_on) < 2 else hands_on


def optimise(recipe: Recipe) -> OffsetMap:
    g = to_graph(recipe.steps)

    offsets: dict[str, int] = {}

    step_map = {s.id: s for s in recipe.steps}

    # layout the steps, starting at the last one
    # such that each step appears before its children
    for sid in reversed(list(nx.topological_sort(g))):
        try:
            offsets[sid] = max(
                offsets[c] + step_map[c].duration for c in g.successors(sid)
            )
        except ValueError:
            # no children
            offsets[sid] = 0

    offset_map = OffsetMap([Offset(off, step_map[sid]) for sid, off in offsets.items()])

    off = 0
    while steps := offset_map.get_steps(off):
        logger.debug(f"{off}: {steps}")
        if not (conflicts := get_conflicts(steps)):
            off += 1
            logger.debug("no conflicts")
            continue

        logger.debug(f"{conflicts=}")

        backtrack = False

        moves, target_offset = offset_map.get_moves(conflicts)
        logger.debug(f"{target_offset} -> {moves}")
        for move in moves:
            backtrack |= offset_map.move_after(move, target_offset)

        if backtrack:
            logger.debug("backtracking")
            off = 0
        else:
            off += 1

    return offset_map.reverse()


GOALS = ("waiting", "total", "both")


def solve(recipe: Recipe, goal: str = "waiting", time_limit: float = 60) -> OffsetMap:
    """
    Exact search with OR-Tools CP-SAT. Waiting = time non-prepable steps sit
    before their next step starts.

    goal="waiting": least waiting, then shortest total time
    goal="total": shortest total time, then least waiting
    goal="both": least waiting + total time, minute for minute
    """
    assert goal in GOALS, goal
    m = cp_model.CpModel()
    horizon = sum(s.duration for s in recipe.steps)
    start = {s.id: m.new_int_var(0, horizon, s.id) for s in recipe.steps}
    end = {s.id: start[s.id] + s.duration for s in recipe.steps}

    for s in recipe.steps:
        for p in s.parents:
            m.add(end[p] <= start[s.id])

    m.add_no_overlap(
        m.new_fixed_size_interval_var(start[s.id], s.duration, f"i{s.id}")
        for s in recipe.steps if not s.hands_off
    )

    waits = []
    for s in recipe.steps:
        kids = [c.id for c in recipe.steps if s.id in c.parents]
        if kids and not s.prepable:
            first = m.new_int_var(0, horizon, f"first{s.id}")
            m.add_min_equality(first, [start[c] for c in kids])
            waits.append(first - end[s.id])

    total = m.new_int_var(0, horizon, "total")
    m.add_max_equality(total, list(end.values()))
    wait = sum(waits)
    # weights bigger than the other term's maximum make it a strict tie-break
    m.minimize(
        {
            "waiting": wait * (horizon + 1) + total,
            "total": total * (horizon * len(waits) + 1) + wait,
            "both": wait + total,
        }[goal]
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.solve(m)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE), solver.status_name(status)
    return OffsetMap([Offset(solver.value(start[s.id]), s) for s in recipe.steps])


def format(optimised: OffsetMap) -> Iterator[str]:
    total = optimised.total_time()

    for x in sorted(optimised.offsets, key=lambda x: x.offset):
        c = "X" if x.step.hands_off else "#"

        prefix = f"[{x.offset:>2} - {x.offset + x.step.duration:>2}]  "
        padding = total - (x.offset + x.step.duration)
        suffix = f"  ({x.step.id}) {x.step.instruction}"

        yield (
            prefix + (" " * x.offset) + (c * x.step.duration) + (" " * padding) + suffix
        )


def main():
    parser = ArgumentParser()
    parser.add_argument("recipe_json", type=FileType("r"))
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--solver", action="store_true", help="use the OR-Tools solver")
    parser.add_argument(
        "--goal",
        choices=GOALS,
        help="what the solver minimises first (default: waiting); implies --solver",
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    recipe = Recipe.from_json(json.load(args.recipe_json))

    if args.solver or args.goal:
        optimised = solve(recipe, args.goal or "waiting")
    else:
        optimised = optimise(recipe)

    for line in format(optimised):
        print(line)


if __name__ == "__main__":
    main()
