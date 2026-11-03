import re

import answer_key

import ichnos


def test_the_answer_key_reads_every_table_view_synonym_and_link():
    key = answer_key.load()
    kinds = [t.kind for t in key.tables.values()]
    assert (
        kinds.count("base table"),
        kinds.count("view"),
        kinds.count("materialized view"),
    ) == (22, 3, 2)
    assert key.synonyms["EMP"] == ("HR", "EMPLOYEES")
    assert len(key.synonyms) == 5
    assert key.links == {"ARCHIVE"}


def test_every_schema_deviation_is_listed_with_its_reason():
    found = set(
        answer_key.score_schema(ichnos.read(answer_key.QUERIES), answer_key.load())
    )
    listed = answer_key.schema_deviations()
    assert sorted(found - listed.keys(), key=str) == []
    assert sorted(listed.keys() - found, key=str) == []
    assert all(
        re.match(r"(ADR \d{4}|README trap): ", reason) for reason in listed.values()
    )


def test_every_lineage_deviation_is_listed_with_its_reason():
    found = set(
        answer_key.score_lineage(
            ichnos.read(answer_key.QUERIES), answer_key.load(), {"DIRECT", "INDIRECT"}
        )
    )
    listed = answer_key.lineage_deviations()
    assert sorted(found - listed.keys()) == []
    assert sorted(listed.keys() - found) == []
    assert all(
        re.match(r"(ADR \d{4}|README trap): ", reason) for reason in listed.values()
    )
