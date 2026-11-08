import json
from pathlib import Path

import pytest

from recipe_optimise import Recipe, brute_force, optimise

RECIPES = ["recipe.json", "spaghetti-with-tomato-sauce.json"]


@pytest.mark.parametrize("optimiser", [optimise, brute_force])
@pytest.mark.parametrize("path", RECIPES)
def test_optimised_timeline_is_valid(path, optimiser):
    recipe = Recipe.from_json(json.loads(Path(__file__).with_name(path).read_text()))
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


@pytest.mark.parametrize("optimiser", [optimise, brute_force])
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
