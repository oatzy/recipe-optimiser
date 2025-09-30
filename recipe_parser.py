#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["ollama"]
# ///

import json
from argparse import ArgumentParser, FileType
from pathlib import Path

import ollama

MODEL_NAME = "llama3"


def parse_recipe(recipe_text: str, system_prompt: str) -> dict:
    """
    Use Ollama to parse a recipe string into a structured JSON object.
    """
    response = ollama.chat(
        model=MODEL_NAME,
        format="json",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": recipe_text},
        ],
    )

    json_string = response["message"]["content"]
    return json.loads(json_string)


def main():
    parser = ArgumentParser()
    parser.add_argument("recipe", type=FileType())

    args = parser.parse_args()

    prompt = Path(__file__).parent.joinpath("system_prompt.txt").read_text()

    parsed_data = parse_recipe(args.recipe.read(), prompt)

    print(json.dumps(parsed_data, indent=2))


if __name__ == "__main__":
    main()
