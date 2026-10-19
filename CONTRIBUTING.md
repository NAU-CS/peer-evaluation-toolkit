# Contributing

This started as one instructor's toolkit for one course. If you adapt it for yours,
improvements are welcome -- especially:

- **Canvas behaviours** not yet in [docs/06-canvas-field-notes.md](docs/06-canvas-field-notes.md).
  Several documented failures return HTTP success while doing nothing; if you find another,
  that is worth more than a feature.
- **Non-NAU adaptations.** The email pattern, the DesignPLUS markup in the Canvas templates,
  and the distribution patterns are all institution-specific. Generalisations welcome.
- **Test cases** for messy student input. `scripts/test_peerreview.py` is the place;
  real examples of what students actually typed are the most valuable contribution here.

## Running the tests

    cd scripts && python3 -m unittest discover -p 'test_*.py' -v

The tests are the spec. `test_scoring.py` pins the factor arithmetic to the worked examples
published in Doerry & Palmer (2011) -- if you change the scoring model, those tests should
fail and you should update them deliberately.

## A note on grade-affecting changes

Anything touching `ags/scoring.py` changes real student grades. Please add a test that
demonstrates the new behaviour, and note in your PR what a student's grade would do
differently under your change.
