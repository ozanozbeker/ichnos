# Report evidence counts and attribute nothing on ambiguity

ichnos reports evidence counts by kind and no confidence score.
A score needs weights, and no answer key on real queries exists to set them.
The prior-art review found no tool whose score measures evidence strength ([issue 19](https://github.com/ozanozbeker/ichnos/issues/19)).

An ambiguous reference adds no evidence to any candidate, and ichnos does not resolve an ambiguity from other queries.
A column missing from every other query does not show that its table lacks the column.
The output lists each candidate's own evidence count beside the ambiguity, so the reader weighs it.

## Considered options

- A score from 0 to 1, or tiers such as weak and strong.
  Rejected because the weights would be guesses.
- A fractional count split across the candidates of an ambiguity.
  Rejected because it picks a reading in part.
- Cross-query resolution, as sqllineage does.
  Rejected for the reason above.
