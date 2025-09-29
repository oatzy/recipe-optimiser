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
        pass


OffsetMap = dict[int, Step]


def optimise(recipe: Recipe) -> OffsetMap:
    pass


def format(optimised: OffsetMap) -> str:
    pass


def main():
    parser = ArgumentParser()
    parser.add_argument("recipe_json", type=FileType)

    args = parser.parse_args()

    recipe = Recipe.from_json(json.load(args.recipe_json))

    optimised = optimise(recipe)

    print(format(optimised))


if __name__ == "__main__":
    main()
