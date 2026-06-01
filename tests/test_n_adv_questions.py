"""Tests for the structural PCC-source-to-canonical converter.

Each test class maps to an acceptance criterion in ``plan.md``. The fixtures
load the raw PCC source files from ``src/pcc_schema/n_adv_templates/`` and run
``convert_pcc_source`` once per test session.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pcc_schema.n_adv_questions import (
    LEAF_WIDGET_TYPES,
    _build_autopopulate_index,
    available_canonical_template_ids,
    convert_pcc_source,
    load_canonical_template,
)

REPO_ROOT = Path(__file__).parent.parent
RAW_DIR = REPO_ROOT / "src" / "pcc_schema" / "n_adv_templates"

# Stable IDs from the raw source files (verified via jq).
BODY_TEMPERATURE_DE_ID = "23f47d86-207b-43f2-b406-0b6c8da247c2"
BLOOD_PRESSURE_DE_ID = "c3b77774-a2c4-42a8-8312-c727e8c81223"
HEARING_AID_DE_ID = "b40a8855-1acd-47a5-a59b-7ea76f6ff74e"
HEART_RATE_CHARACTER_DE_ID = "c1b18a95-1659-4899-b99f-f28d12999942"
HEART_RATE_CHARACTER_WIDGET_ID = "1fc078f7-fda0-4ab5-a36b-93895a13b742"
# "Respiratory: shortness of breath" select widget; "z" = "None of the above".
# The AP - SOB none of the above - MDS rule fans that option out to the MDS
# "Shortness of breath (none of the above)" checkbox at f4c62b20-...
SOB_SELECT_WIDGET_ID = "ccd0178f-1f48-4818-8615-5fb3696bb873"
SOB_NONE_MDS_TARGET = "f4c62b20-6652-4e12-9b26-0f8bab4f3180"
MOBILITY_DE_IDS = {
    "00e03579-b6ed-453c-a541-ab55a413fe40",  # Cane/Crutch
    "51fd73ee-c7ed-41d9-a2d8-b70bf8b13c48",  # Walker
    "75a16c35-f329-4baf-93ed-07bdcf7c9ebe",  # Electric Wheelchair
    "eaf02414-900b-42de-a5a4-12492d1a4fa5",  # Manual Wheelchair
    "efa9e896-d4ac-40ae-922e-352549a3091b",  # Limb Prosthesis
    "4b764da3-49b8-4d77-a02b-720134d1f00b",  # Prosthesis location
    "6386b5c0-ca93-4ed4-9eed-5d283e477f20",  # Other mobility device
}

EXPECTED_IMAGEMAPS = {
    "Skin Issues": 40,
    "Lung Issues": 30,
    "Pain Issues": 10,
    "Edema issues": 10,
}


@pytest.fixture(scope="module")
def skilled_canonical() -> dict[str, Any]:
    return _convert(RAW_DIR / "N_Adv_-_Skilled_Evaluation.json")


@pytest.fixture(scope="module")
def admission_canonical() -> dict[str, Any]:
    return _convert(RAW_DIR / "N_Adv_-_Clinical_Admission.json")


def _convert(raw_path: Path) -> dict[str, Any]:
    with raw_path.open(encoding="utf-8") as f:
        return dict(convert_pcc_source(json.load(f)))


def _section(canonical: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [
        s for s in canonical["sections"] if s["sectionDescription"] == name
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 section named {name!r}, got {len(matches)}"
    )
    return matches[0]


def _questions_in_section(section: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        q
        for group in section["assessmentQuestionGroups"]
        for q in group["questions"]
    ]


def _all_questions(canonical: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for section in canonical["sections"]:
        out.extend(_questions_in_section(section))
        for repeat in section["repeatedQuestionGroups"]:
            out.extend(repeat["questions"])
    return out


class TestImageMapDetection:
    """Acceptance criterion 2: all 4 imageMaps detected with correct slot counts."""

    def test_skilled(self, skilled_canonical: dict[str, Any]) -> None:
        actual = {
            r["slotKind"]: r["slotCount"]
            for s in skilled_canonical["sections"]
            for r in s["repeatedQuestionGroups"]
        }
        assert actual == EXPECTED_IMAGEMAPS

    def test_admission(self, admission_canonical: dict[str, Any]) -> None:
        actual = {
            r["slotKind"]: r["slotCount"]
            for s in admission_canonical["sections"]
            for r in s["repeatedQuestionGroups"]
        }
        assert actual == EXPECTED_IMAGEMAPS


class TestSkinSection:
    """Acceptance criterion 1: Skin -> 1 repeatedQuestionGroup, slotCount=40, ~104 questions."""

    def test_skin_repeated_group(self, skilled_canonical: dict[str, Any]) -> None:
        skin = _section(skilled_canonical, "Skin")
        assert len(skin["repeatedQuestionGroups"]) == 1
        group = skin["repeatedQuestionGroups"][0]
        assert group["slotKind"] == "Skin Issues"
        assert group["slotCount"] == 40
        assert 100 <= len(group["questions"]) <= 110
        # Every per-slot question carries the imageMap's parent dataElementId.
        assert all(
            q["dataElementId"] == group["dataElementId"]
            for q in group["questions"]
        )


class TestBodyTemperature:
    """Acceptance criterion 3: Body Temperature -> 2 separate questions, not 1."""

    def test_split(self, skilled_canonical: dict[str, Any]) -> None:
        vitals = _section(skilled_canonical, "Vitals")
        bt_questions = [
            q
            for q in _questions_in_section(vitals)
            if q["dataElementId"] == BODY_TEMPERATURE_DE_ID
        ]
        assert len(bt_questions) == 2
        assert sorted(q["widgetType"] for q in bt_questions) == [
            "select",
            "textbox",
        ]


class TestQuestionTextEnrichment:
    """questionText is composed as '<section>: <dataElement> (<widget label>)'.

    Without this prefix, widget labels like "Systolic" / "Diastolic" /
    "Location" carry no clinical context to a downstream LLM. The enrichment
    makes each row self-describing.
    """

    def test_blood_pressure(self, skilled_canonical: dict[str, Any]) -> None:
        vitals = _section(skilled_canonical, "Vitals")
        bp = [
            q
            for q in _questions_in_section(vitals)
            if q["dataElementId"] == BLOOD_PRESSURE_DE_ID
        ]
        labels = {q["questionText"] for q in bp}
        assert "Vitals: Blood Pressure (Systolic)" in labels
        assert "Vitals: Blood Pressure (Diastolic)" in labels

    def test_heart_rate_character_dedupes_when_label_equals_parent(
        self, skilled_canonical: dict[str, Any]
    ) -> None:
        # Heart Rate Character dataElement contains a single select whose
        # label IS "Heart Rate Character" -- the parenthetical should collapse.
        vitals = _section(skilled_canonical, "Vitals")
        hrc = [
            q
            for q in _questions_in_section(vitals)
            if q["dataElementId"] == HEART_RATE_CHARACTER_DE_ID
        ]
        assert len(hrc) == 1
        assert hrc[0]["questionText"] == "Vitals: Heart Rate Character"

    def test_skin_repeated_carries_slot_kind(
        self, skilled_canonical: dict[str, Any]
    ) -> None:
        skin = _section(skilled_canonical, "Skin")
        repeat = skin["repeatedQuestionGroups"][0]
        # Pick a recognisable per-slot question (Location is the imageMap's
        # anatomical select).
        locations = [
            q for q in repeat["questions"] if q["questionText"].endswith("(Location)")
        ]
        assert locations, "expected a Location question inside Skin Issues slot"
        assert locations[0]["questionText"] == "Skin: Skin Issues (Location)"


class TestHearingAid:
    """Acceptance criterion 4: Hearing Aid(s) -> 3 inner checkboxes flattened to 3 questions."""

    def test_hearing_aid(self, admission_canonical: dict[str, Any]) -> None:
        eent = _section(admission_canonical, "EENT")
        hearing_aid = [
            q
            for q in _questions_in_section(eent)
            if q["dataElementId"] == HEARING_AID_DE_ID
        ]
        assert len(hearing_aid) == 3
        assert all(q["widgetType"] == "checkbox" for q in hearing_aid)
        # Enriched questionText: "<section>: <parent> (<widget label>)";
        # the inner-checkbox label dedupe folds the "Hearing Aid(s)" widget
        # against the "Hearing Aid(s) - Care Profile" parent (they differ, so
        # both appear) — we just assert the section + parent prefix is there.
        for q in hearing_aid:
            assert q["questionText"].startswith(
                "EENT: Hearing Aid(s) - Care Profile"
            )
        labels = {q["questionText"] for q in hearing_aid}
        assert labels == {
            "EENT: Hearing Aid(s) - Care Profile (Hearing Aid(s))",
            "EENT: Hearing Aid(s) - Care Profile (Left)",
            "EENT: Hearing Aid(s) - Care Profile (Right)",
        }


class TestMobilityStaysSeparate:
    """Acceptance criterion 5: Mobility area kept as 7 separate questions, NOT regrouped."""

    def test_mobility_separate(self, admission_canonical: dict[str, Any]) -> None:
        other = _section(admission_canonical, "Other")
        mobility = [
            q
            for q in _questions_in_section(other)
            if q["dataElementId"] in MOBILITY_DE_IDS
        ]
        # 7 dataElements -> 7 questions (each composition has exactly 1 leaf widget)
        assert len(mobility) == len(MOBILITY_DE_IDS)
        # No synthetic "Mobility Devices" multi-select.
        assert not any(
            q["questionText"] == "Mobility Devices" for q in mobility
        )


class TestSectionOrder:
    """Acceptance criterion 6: section names + order match the raw source."""

    def test_skilled_section_order(self, skilled_canonical: dict[str, Any]) -> None:
        names = [s["sectionDescription"] for s in skilled_canonical["sections"]]
        assert names[:5] == [
            "Vitals",
            "Pain",
            "Neurologic",
            "EENT",
            "Mental Status",
        ]
        assert "Skin" in names
        # sectionSequence is 1-based and contiguous (after MDS drop).
        seqs = [s["sectionSequence"] for s in skilled_canonical["sections"]]
        assert seqs == list(range(1, len(seqs) + 1))


class TestMDSSectionDropped:
    """Acceptance criterion 9: MDS section is dropped because it's 100% autopopulated."""

    def test_mds_absent(self, skilled_canonical: dict[str, Any]) -> None:
        names = [s["sectionDescription"] for s in skilled_canonical["sections"]]
        assert "MDS" not in names


class TestResponseOptionTargetQuestionKeys:
    """Each canonical responseOption carries the MDS-target widget UUIDs
    that the autoPopulate rules fill in when that option is picked.
    Without this mapping, scoring against actuals keyed by the
    materialized exploded-checkbox UUID has nothing to match against
    the canonical select+option rule the operator authored."""

    def test_sob_none_of_the_above_maps_to_mds_checkbox(
        self, skilled_canonical: dict[str, Any]
    ) -> None:
        # Walk all canonical questions, find the Respiratory SOB select.
        sob = None
        for s in skilled_canonical["sections"]:
            for g in s["assessmentQuestionGroups"]:
                for q in g["questions"]:
                    if q["questionKey"] == SOB_SELECT_WIDGET_ID:
                        sob = q
                        break
        assert sob is not None, "expected canonical SOB select"
        # Locate the "z" (None of the above) option.
        z_opt = next(
            (o for o in sob["responseOptions"] if o["responseValue"] == "z"),
            None,
        )
        assert z_opt is not None
        assert SOB_NONE_MDS_TARGET in z_opt["targetQuestionKeys"], (
            f"expected MDS target {SOB_NONE_MDS_TARGET} on the 'z' option"
        )

    def test_options_without_autopopulate_have_empty_targets(
        self, skilled_canonical: dict[str, Any]
    ) -> None:
        # The "Position" select on Blood Pressure doesn't drive MDS — its
        # responseOptions should all carry targetQuestionKeys=[].
        for s in skilled_canonical["sections"]:
            if s["sectionDescription"] != "Vitals":
                continue
            for q in (
                q for g in s["assessmentQuestionGroups"] for q in g["questions"]
            ):
                if (
                    q["dataElementId"] == BLOOD_PRESSURE_DE_ID
                    and "Position" in q["questionText"]
                ):
                    for opt in q["responseOptions"]:
                        assert opt["targetQuestionKeys"] == []
                    return
        # If we never found Blood Pressure's Position select, fail loudly
        # so the test doesn't silently regress to "no asserts ran".
        raise AssertionError("did not encounter Blood Pressure Position")


class TestAutoPopulateFlag:
    """Acceptance criterion 10: autoPopulate machinery is wired through correctly.

    In both N Adv templates, every autoPopulate target sits in a dataElement
    referenced exclusively from the MDS section -- so once MDS is dropped, the
    canonical output has zero autopopulated questions. We still exercise the
    indexer directly to confirm it isn't broken.
    """

    def test_ap_index_extracts_corrective_lenses_mds(self) -> None:
        # Direct unit test on the indexer using the Corrective Lenses rule
        # we verified by hand against the raw source.
        rules = [
            {
                "name": "AP: Corrective Lenses - MDS",
                "action": [
                    {
                        "name": "autoPopulate",
                        "path": "3c2056ad-1752-44d5-8aac-1b27d0bbf90b",
                        "value": "1",
                    }
                ],
                "conditions": [
                    {
                        "conditionOrConditions": [
                            {
                                "type": "condition",
                                "path": "b47d9528-7708-4dcd-a0a8-d1db17de4228",
                                "operation": "eq",
                                "value": "1",
                            }
                        ]
                    }
                ],
            }
        ]
        index = _build_autopopulate_index(rules)
        assert index == {
            "3c2056ad-1752-44d5-8aac-1b27d0bbf90b": [
                "b47d9528-7708-4dcd-a0a8-d1db17de4228"
            ]
        }

    def test_ap_index_merges_multi_source_targets(self) -> None:
        rules = [
            {
                "action": [{"name": "autoPopulate", "path": "TARGET"}],
                "conditions": [
                    {"type": "condition", "path": "SRC_A"},
                    {"type": "condition", "path": "SRC_B"},
                ],
            },
            {
                "action": [{"name": "autoPopulate", "path": "TARGET"}],
                "conditions": [{"type": "condition", "path": "SRC_C"}],
            },
        ]
        index = _build_autopopulate_index(rules)
        assert index == {"TARGET": ["SRC_A", "SRC_B", "SRC_C"]}

    def test_canonical_output_has_no_autopopulated_questions(
        self, skilled_canonical: dict[str, Any]
    ) -> None:
        # All autoPopulate targets in N Adv live under the MDS-only path
        # (verified via offline tracing), so once MDS is dropped none remain.
        autopopulated = [
            q for q in _all_questions(skilled_canonical) if q["isAutoPopulated"]
        ]
        assert autopopulated == []

    def test_non_autopopulated_question_has_empty_sources(
        self, skilled_canonical: dict[str, Any]
    ) -> None:
        vitals = _section(skilled_canonical, "Vitals")
        bt_questions = [
            q
            for q in _questions_in_section(vitals)
            if q["dataElementId"] == BODY_TEMPERATURE_DE_ID
        ]
        assert bt_questions
        for q in bt_questions:
            assert q["isAutoPopulated"] is False
            assert q["sourceQuestionKeys"] == []


class TestQuestionKeyIsWidgetId:
    """Acceptance criterion 7: questionKey is the widget's id, not the dataElementId."""

    def test_heart_rate_character(self, skilled_canonical: dict[str, Any]) -> None:
        vitals = _section(skilled_canonical, "Vitals")
        hrc = [
            q
            for q in _questions_in_section(vitals)
            if q["dataElementId"] == HEART_RATE_CHARACTER_DE_ID
        ]
        assert len(hrc) == 1
        assert hrc[0]["questionKey"] == HEART_RATE_CHARACTER_WIDGET_ID
        assert hrc[0]["questionKey"] != hrc[0]["dataElementId"]


class TestQuestionCount:
    """Acceptance criterion 8: total leaf question count after MDS drop."""

    def test_skilled_total(self, skilled_canonical: dict[str, Any]) -> None:
        # Source has 594 leaf widgets; MDS contributes 47, dropped here.
        # Expected: ~547. Allow a small margin for any edge-case skips.
        assert 540 <= len(_all_questions(skilled_canonical)) <= 555

    def test_admission_total(self, admission_canonical: dict[str, Any]) -> None:
        # Source has 588 leaf widgets; some sections may be dropped here too.
        # Loose bound -- exact number is observed in the generated output.
        assert 400 <= len(_all_questions(admission_canonical)) <= 595


class TestCanonicalLoader:
    """The consumer-facing helpers used by chart-mapping."""

    def test_available_ids(self) -> None:
        assert available_canonical_template_ids() == [703058, 703168]

    def test_load_skilled(self) -> None:
        canon = load_canonical_template(703058)
        assert canon["templateName"] == "N Adv - Skilled Evaluation"
        assert "Skin" in [s["sectionDescription"] for s in canon["sections"]]
        assert "MDS" not in [s["sectionDescription"] for s in canon["sections"]]

    def test_load_admission(self) -> None:
        canon = load_canonical_template(703168)
        assert canon["templateName"] == "N Adv - Clinical Admission"

    def test_load_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="No canonical template"):
            load_canonical_template(99999999)


class TestQuestionShape:
    """Every emitted question has the required keys and a valid widget type."""

    def test_required_keys(self, skilled_canonical: dict[str, Any]) -> None:
        required = {
            "questionKey",
            "dataElementId",
            "questionText",
            "widgetType",
            "required",
            "responseOptions",
            "isAutoPopulated",
            "sourceQuestionKeys",
        }
        for q in _all_questions(skilled_canonical):
            assert required <= q.keys()
            assert q["widgetType"] in LEAF_WIDGET_TYPES
            assert q["questionKey"]  # non-empty
            assert q["dataElementId"]  # non-empty
            assert isinstance(q["responseOptions"], list)
            assert isinstance(q["isAutoPopulated"], bool)
            assert isinstance(q["sourceQuestionKeys"], list)
