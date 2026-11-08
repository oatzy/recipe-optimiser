# recipe-optimiser

Given a recipe with steps that run in parallel, find the 'optimal' sequence of operations.

An ordering is considered optimal if

1. No steps conflict, requiring multiple 'hands-on' actions at once
2. Steps are completed as close to 'on time' as possible; nothing is at rusk of burning or going cold
3. The total cooking time is minimised, subject to (1) and (2)


## Usage

Convert a recipe to JSON with the Claude Code skill `/parse-recipe <recipe.txt>`, then run `uv run recipe_optimise.py <recipe>.json`.

Run the tests with `uv run --with pytest --with networkx pytest`.
