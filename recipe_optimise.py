#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["networkx"]
# ///

import json

from argparse import ArgumentParser, FileType
from collections import deque
from dataclasses import dataclass, field

import networkx as nx


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

    def to_graph(self) -> nx.DiGraph:
        g = nx.DiGraph()
        for s in self.steps:
            for p in s.parents:
                g.add_edge(p, s.id)
        return g


@dataclass
class Offset:
    offset: int
    step: Step


@dataclass
class OffsetMap:
    offsets: list[Offset]

    def __post_init__(self):
        self._map: dict[str, Offset] = {x.step.id: x for x in self.offsets}

    def get_steps(self, pos: int) -> list[Step]:
        return [
            x.step for x in self.offsets if x.offset <= pos < x.offset + x.step.duration
        ]

    def get_moves(self, steps: list[Step]) -> tuple[list[Step], int]:
        if not (possible_sticks := [s for s in steps if not s.prepable]):
            possible_sticks = steps

        stick = min(possible_sticks, key=lambda s: s.duration + self._map[s.id].offset)

        return [s for s in steps if s != stick], stick.duration

    def move_after(self, step: Step, target: int):
        distance = target - self._map[step.id].offset
        self.move(step, distance)

    def move(self, step: Step, distance: int):
        # a step may be the parent of multiple steps
        # but only want to move it once
        seen: set[str] = set()
        parents = deque([step.id])

        while parents:
            sid = parents.pop()

            if sid in seen:
                continue

            off = self._map[sid]
            off.offset += distance

            parents.extendleft(off.step.parents)

        # TODO: if the step isn't prepable
        # we should also pull forward its children

    def total_time(self) -> int:
        return max(x.offset + x.step.duration for x in self.offsets)

    def reverse(self) -> "OffsetMap":
        total = self.total_time()
        return OffsetMap(
            [Offset(total - x.offset - x.step.duration, x.step) for x in self.offsets]
        )


def get_conflicts(steps: list[Step]) -> list[Step] | None:
    hands_on = [s for s in steps if not s.hands_off]
    return None if len(hands_on) < 2 else hands_on


def optimise(recipe: Recipe) -> OffsetMap:
    g = recipe.to_graph()

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
        if not (conflicts := get_conflicts(steps)):
            off += 1
            continue

        moves, target_offset = offset_map.get_moves(conflicts)
        for move in moves:
            offset_map.move_after(move, target_offset)

        off += 1

    return offset_map.reverse()


def format(optimised: OffsetMap) -> str:
    # TODO: format something like git log --graph
    return "\n".join(
        f"{x.offset:>3}: {x.step.id}"
        for x in sorted(optimised.offsets, key=lambda x: x.offset)
    )


def main():
    parser = ArgumentParser()
    parser.add_argument("recipe_json", type=FileType("r"))

    args = parser.parse_args()

    recipe = Recipe.from_json(json.load(args.recipe_json))

    optimised = optimise(recipe)

    print(format(optimised))


if __name__ == "__main__":
    main()
