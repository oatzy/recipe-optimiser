import json
from functools import partial
from pathlib import Path

import pytest

from recipe_optimise import GOALS, Recipe, optimise, solve

RECIPES = ["recipe.json", "spaghetti-with-tomato-sauce.json"] + sorted(
    str(p.relative_to(Path(__file__).parent))
    for p in Path(__file__).with_name("recipes").glob("*.json")
)
OPTIMISERS = [optimise] + [partial(solve, goal=g) for g in GOALS]


def load(path):
    return Recipe.from_json(json.loads((Path(__file__).parent / path).read_text()))


def waiting(timeline):
    t = {x.step.id: x for x in timeline.offsets}
    total = 0
    for x in t.values():
        kids = [c.offset for c in t.values() if x.step.id in c.step.parents]
        if kids and not x.step.prepable:
            total += min(kids) - (x.offset + x.step.duration)
    return total


@pytest.mark.parametrize("optimiser", OPTIMISERS)
@pytest.mark.parametrize("path", RECIPES)
def test_optimised_timeline_is_valid(path, optimiser):
    recipe = load(path)
    timeline = {x.step.id: x for x in optimiser(recipe).offsets}

    assert timeline.keys() == {s.id for s in recipe.steps}

    for x in timeline.values():
        for p in x.step.parents:
            parent = timeline[p]
            assert parent.offset + parent.step.duration <= x.offset, (p, x.step.id)

    hands_on = [x for x in timeline.values() if not x.step.hands_off]
    for i, a in enumerate(hands_on):
        for b in hands_on[i + 1 :]:
            overlap = a.offset < b.offset + b.step.duration and b.offset < a.offset + a.step.duration
            assert not overlap, (a.step.id, b.step.id)


@pytest.mark.parametrize("optimiser", OPTIMISERS)
def test_isolated_step_is_kept(optimiser):
    recipe = Recipe.from_json(
        {
            "steps": [
                {"id": "1", "duration": 2},
                {"id": "2", "duration": 3, "parents": ["1"]},
                {"id": "3", "duration": 1},
            ]
        }
    )
    assert {x.step.id for x in optimiser(recipe).offsets} == {"1", "2", "3"}


@pytest.mark.parametrize("path", RECIPES)
def test_each_goal_wins_on_its_own_measure(path):
    recipe = load(path)
    plans = {g: solve(recipe, g) for g in GOALS}
    assert plans["total"].total_time() == min(p.total_time() for p in plans.values())
    assert waiting(plans["waiting"]) == min(waiting(p) for p in plans.values())
    both = {g: waiting(p) + p.total_time() for g, p in plans.items()}
    assert both["both"] == min(both.values())
