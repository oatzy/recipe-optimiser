#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["networkx"]
# ///

import json

from argparse import ArgumentParser, FileType
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


OffsetMap = dict[int, Step]


def optimise(recipe: Recipe) -> OffsetMap:
    g = recipe.to_graph()

    offsets = {}

    steps = {s.id: s for s in recipe.steps}

    for sid in reversed(list(nx.topological_sort(g))):
        try:
            offsets[sid] = max(
                offsets[c] + steps[c].duration for c in g.successors(sid)
            )
        except ValueError:
            # no children
            offsets[sid] = 0

    # TODO: resolve conflicts

    return offsets


def format(optimised: OffsetMap) -> str:
    return "\n".join(
        f"{offset:>3}: {sid}"
        for sid, offset in sorted(optimised.items(), key=lambda x: x[1])
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
