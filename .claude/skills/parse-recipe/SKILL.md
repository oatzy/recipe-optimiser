---
name: parse-recipe
description: Convert a recipe (text file, pasted text or URL) into the step JSON that recipe_optimise.py takes, then run the optimiser on it. Use when asked to parse, convert or optimise a recipe.
---

# Parse a recipe into optimiser JSON

## Input
A recipe as a file path, pasted text or URL. If none is given, ask for one.

## Output format
Write `<recipe-slug>.json` in the repo root (unless the user names a path):

```json
{
  "name": "Recipe name",
  "steps": [
    {
      "id": "1a",
      "instruction": "Bring a large saucepan of water to the boil",
      "duration": 5,
      "parents": [],
      "hands_off": true,
      "prepable": false
    }
  ]
}
```

Each step may only have these keys, because `recipe_optimise.py` builds steps with `Step(**step)` and crashes on anything else:

| key | type | meaning |
|---|---|---|
| `id` | string | Recipe step number plus a letter when a step is split: `1a`, `1b`, `2a`. Must be unique. |
| `instruction` | string | A short imperative taken from the recipe text. |
| `duration` | int | Minutes, at least 1. Use the upper bound of a range. |
| `parents` | string[] | Ids of steps that must *finish* before this one starts. List only direct dependencies, not ancestors. |
| `hands_off` | bool | `true` if the step needs no attention (oven, boiling, simmering, preheating, resting). |
| `prepable` | bool | `true` if it can be done well in advance with no loss (chopping, grating, mixing a dry rub). |

## Rules
1. **Split compound instructions** into one step per action, especially when the actions can run in parallel. For example, "While the pasta cooks, heat oil and fry the onion" becomes cook pasta, heat oil, and fry onion (parent: heat oil).
2. **Include implied waiting steps** that the recipe skips over but that take time: preheating the oven, bringing water to the boil, heating oil in a pan. Make them separate steps and put them before the step that needs them. Also add prep that only appears in the ingredients list ("2 cloves garlic, finely chopped") as prepable steps with ids `0a`, `0b`, and so on. If two parts of the dish are served together, add a final "Serve" step that depends on both, so they finish at the same time. Don't invent any other steps.
3. **Estimate untimed steps realistically, for a home cook rather than a chef.** For example: chop an onion 4-5, mince garlic 2, heat oil 2, boil a large pan of water 10, preheat the oven 10, drain 1, serve 1. For "cook according to the packet", use a typical time for that food (dried spaghetti 10, rice 20).
4. **Get dependencies from what each step actually needs, not from the order it's written in.** Prep steps usually have no parents. "Once X is cooked" means X is a parent.
5. Treat a long passive step with occasional stirring ("simmer 10 min, stirring occasionally") as one hands-off step. Don't model the stirring.
6. The steps must form a DAG (no cycles), every parent id must exist, and the final step (usually "Serve") should depend, directly or indirectly, on everything.

## Verify
Run the optimiser on the file:

```sh
uv run recipe_optimise.py <file>.json
```

If it errors, fix the JSON and run it again. Show the user the timeline, and list every duration you estimated and every implied step you added, so they can correct them.
