# Contributing to AwesomePPT

Start with the [quick start](README.md#build-your-first-deck) and the [editable examples](docs/gallery.md). Issues and pull requests are welcome in English or Chinese.

## Report a rendering or data problem

Include the mode and style, the Python and PowerPoint or LibreOffice versions, and the smallest shareable slide plan and CSV that reproduce the issue. Say which slide, object or value changed, what you expected, and what appeared in the actual projection. Synthetic replacements are welcome when the original material is private.

## Change a template or renderer

The portable skill lives in `research-deck/`. Visual tokens live in `assets/styles.json`, narrative choices in `assets/modes.json`, and complete demo inputs in `assets/starters/`, all relative to that directory. The root `.gitignore` admits named distribution directories so that a mixed research workspace can be maintained safely. Place shareable examples under `examples/` and their rendered files in `docs/decks/`.

Run the following from the repository root after installing the Python dependencies. The second command uses LibreOffice, Pandoc and Chinese fonts.

```sh
python research-deck/evals/test_deck.py
python .github/check_showcase.py
```

When a starter changes, rebuild its shipped PPTX. When either showcased talk changes, rebuild its PPTX and PDF. Re-render the README images for changes that affect the illustrated pages.

```sh
python research-deck/scripts/deck.py build research-deck/assets/starters/acceptance.json docs/decks/acceptance.pptx --replace
python research-deck/scripts/deck.py build examples/iris/deck.json docs/decks/iris.pptx --replace
python research-deck/scripts/deck.py preview docs/decks/iris.pptx docs/decks/iris.pdf --replace
python docs/render_gallery.py --fonts /usr/share/fonts/truetype/dejavu
```

For a new dataset or figure, include the creator, license, stable source locator, original input and a short account of transformations. Describe the intended reader and provide one rendered example when proposing a new layout. Use the [pull request checklist](.github/pull_request_template.md) to record what you tested.
