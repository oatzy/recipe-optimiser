#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["networkx"]
# ///

import json
import logging

from argparse import ArgumentParser, FileType
from collections import deque
from dataclasses import dataclass, field
from typing import Iterator

import networkx as nx

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

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    recipe = Recipe.from_json(json.load(args.recipe_json))

    optimised = optimise(recipe)

    for line in format(optimised):
        print(line)


if __name__ == "__main__":
    main()
