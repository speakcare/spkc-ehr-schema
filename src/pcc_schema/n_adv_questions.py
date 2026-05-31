"""
Convert a raw PCC source-template JSON into the canonical N-Adv form.

The raw form (one per template in ``n_adv_templates/``) is what PCC exports from
its template editor. Each clinical concept is written once; repeated-slot widgets
like wound/pain/lung/edema use an ``imageMap`` with ``maxIssues`` to indicate the
slot count, and the per-slot field tree lives at
``imageMap.imageMapControls.composition``.

This module produces a structurally faithful canonical form: one question per
leaf input widget, repeated-slot widgets emitted as a single
``repeatedQuestionGroup`` carrying ``slotKind`` and ``slotCount``. No clinical
regrouping (e.g. collapsing "Mobility Devices" sibling booleans into a single
multi-select) happens here -- that's the future grouping pass, which consumes an
HTML-derived spec.

CLI: ``python -m pcc_schema.n_adv_questions`` regenerates the canonical files in
``assmnt_templates/`` from every raw template under ``n_adv_templates/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

LEAF_WIDGET_TYPES: frozenset[str] = frozenset(
    {"checkbox", "radio", "select", "textbox", "date"}
)
CONTAINER_TYPES: frozenset[str] = frozenset(
    {"container", "imageMapControlsSection"}
)


class ResponseOption(TypedDict):
    responseText: str
    responseValue: str


class Question(TypedDict):
    questionKey: str
    dataElementId: str
    questionText: str
    widgetType: str
    required: bool
    responseOptions: list[ResponseOption]
    isAutoPopulated: bool
    sourceQuestionKeys: list[str]


class RepeatedQuestionGroup(TypedDict):
    slotKind: str
    slotCount: int
    dataElementId: str
    imageMapId: str
    questions: list[Question]


class AssessmentQuestionGroup(TypedDict):
    groupNumber: str
    groupTitle: str
    questions: list[Question]


class CanonicalSection(TypedDict):
    sectionDescription: str
    sectionSequence: int
    assessmentQuestionGroups: list[AssessmentQuestionGroup]
    repeatedQuestionGroups: list[RepeatedQuestionGroup]


class CanonicalTemplate(TypedDict):
    templateId: str
    templateName: str
    templateVersion: Any
    sections: list[CanonicalSection]


@dataclass
class _WalkResult:
    questions: list[Question] = field(default_factory=list)
    repeats: list[RepeatedQuestionGroup] = field(default_factory=list)

    def extend(self, other: "_WalkResult") -> None:
        self.questions.extend(other.questions)
        self.repeats.extend(other.repeats)


def convert_pcc_source(source: dict[str, Any]) -> CanonicalTemplate:
    """Convert a raw PCC source-template dict to its canonical form."""
    de_index: dict[str, dict[str, Any]] = {
        de["dataElementId"]: de
        for de in source.get("usedDataElements", {}).get("dataElements", [])
        if de.get("dataElementId")
    }
    ap_index = _build_autopopulate_index(source.get("rules", []) or [])
    raw_sections = [
        _walk_section(section, de_index, ap_index)
        for section in source.get("sections", [])
    ]
    # Drop sections where every question is autopopulated (PCC's UI hides them
    # because there's nothing for a user to fill in -- e.g. the MDS section).
    kept = [s for s in raw_sections if not _is_fully_autopopulated(s)]
    # Reassign sectionSequence so it stays 1-based and contiguous.
    for idx, section in enumerate(kept, start=1):
        section["sectionSequence"] = idx
    return {
        "templateId": source["templateId"],
        "templateName": source.get("name", ""),
        "templateVersion": source.get("version", ""),
        "sections": kept,
    }


def _build_autopopulate_index(
    rules: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Map target widget id -> sorted unique list of source widget ids.

    A rule with ``action[].name == "autoPopulate"`` derives the target widget
    (``action[].path``) from values of one or more source widgets, which appear
    as ``condition.path`` entries anywhere inside ``rule.conditions`` (the
    block nests under ``conditionOrConditions`` and can be further nested by
    ``logic`` wrappers).
    """
    index: dict[str, set[str]] = {}
    for rule in rules:
        targets = [
            action.get("path")
            for action in (rule.get("action") or [])
            if isinstance(action, dict)
            and action.get("name") == "autoPopulate"
            and action.get("path")
        ]
        if not targets:
            continue
        sources = _collect_condition_paths(rule.get("conditions"))
        for target in targets:
            index.setdefault(target, set()).update(sources)
    return {target: sorted(sources) for target, sources in index.items()}


def _collect_condition_paths(node: Any) -> set[str]:
    """Recursively gather every ``condition.path`` from a rule conditions tree."""
    paths: set[str] = set()
    if isinstance(node, dict):
        if node.get("type") == "condition" and node.get("path"):
            paths.add(node["path"])
        for value in node.values():
            paths.update(_collect_condition_paths(value))
    elif isinstance(node, list):
        for item in node:
            paths.update(_collect_condition_paths(item))
    return paths


def _is_fully_autopopulated(section: CanonicalSection) -> bool:
    """True if the section has at least one question and every one is autopopulated."""
    questions: list[Question] = [
        q
        for group in section["assessmentQuestionGroups"]
        for q in group["questions"]
    ] + [
        q
        for repeat in section["repeatedQuestionGroups"]
        for q in repeat["questions"]
    ]
    return bool(questions) and all(q["isAutoPopulated"] for q in questions)


def _walk_section(
    section: dict[str, Any],
    de_index: dict[str, dict[str, Any]],
    ap_index: dict[str, list[str]],
) -> CanonicalSection:
    assessment_groups: list[AssessmentQuestionGroup] = []
    repeated_groups: list[RepeatedQuestionGroup] = []
    for group_idx, group in enumerate(section.get("groups", []), start=1):
        result = _walk_contents(group.get("contents", []), de_index, ap_index)
        if result.questions:
            assessment_groups.append(
                {
                    "groupNumber": str(group_idx),
                    "groupTitle": group.get("name") or "",
                    "questions": result.questions,
                }
            )
        repeated_groups.extend(result.repeats)
    return {
        "sectionDescription": section.get("name") or "",
        "sectionSequence": 0,  # reassigned after section-drop filter
        "assessmentQuestionGroups": assessment_groups,
        "repeatedQuestionGroups": repeated_groups,
    }


def _walk_contents(
    contents: list[dict[str, Any]],
    de_index: dict[str, dict[str, Any]],
    ap_index: dict[str, list[str]],
) -> _WalkResult:
    result = _WalkResult()
    for content in contents:
        t = content.get("type")
        if t == "dataElement":
            ref_id = content.get("refDataElementId")
            if not ref_id:
                # Heading-only dataElement (no refDataElementId): the visual
                # label that the grouping pass will use to cluster siblings.
                # The structural pass emits nothing for it.
                continue
            de = de_index.get(ref_id)
            if de is None:
                continue
            result.extend(
                _walk_composition(de.get("composition", []), de, ap_index)
            )
        elif t == "dataElementLayout":
            result.extend(
                _walk_contents(
                    content.get("dataElements", []), de_index, ap_index
                )
            )
    return result


def _walk_composition(
    composition: list[dict[str, Any]],
    parent_de: dict[str, Any],
    ap_index: dict[str, list[str]],
) -> _WalkResult:
    result = _WalkResult()
    de_id = parent_de.get("dataElementId", "")
    for entry in composition:
        t = entry.get("type")
        if t == "imageMap":
            inner = _walk_composition(
                entry.get("imageMapControls", {}).get("composition", []),
                parent_de,
                ap_index,
            )
            result.repeats.append(
                {
                    "slotKind": parent_de.get("name", ""),
                    "slotCount": int(entry.get("maxIssues", 0)),
                    "dataElementId": de_id,
                    "imageMapId": entry.get("id", ""),
                    "questions": inner.questions,
                }
            )
        elif t in LEAF_WIDGET_TYPES:
            widget_id = entry.get("id") or ""
            sources = ap_index.get(widget_id, [])
            result.questions.append(
                {
                    "questionKey": widget_id,
                    "dataElementId": de_id,
                    "questionText": entry.get("label") or entry.get("name") or "",
                    "widgetType": str(t),
                    "required": bool(entry.get("required", False)),
                    "responseOptions": [
                        {
                            "responseText": str(opt.get("text", "")),
                            "responseValue": str(opt.get("value", "")),
                        }
                        for opt in (entry.get("options") or [])
                    ],
                    "isAutoPopulated": bool(sources),
                    "sourceQuestionKeys": list(sources),
                }
            )
        elif t in CONTAINER_TYPES:
            result.extend(
                _walk_composition(entry.get("composition", []), parent_de, ap_index)
            )
    return result


_PACKAGE_DIR = Path(__file__).parent
_RAW_DIR = _PACKAGE_DIR / "n_adv_templates"
_CANONICAL_DIR = _PACKAGE_DIR / "assmnt_templates"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


def _dump_json(data: CanonicalTemplate, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def regenerate_all(
    raw_dir: Path = _RAW_DIR, out_dir: Path = _CANONICAL_DIR
) -> list[Path]:
    """Convert every raw template under ``raw_dir`` to a ``*_canonical.json``."""
    written: list[Path] = []
    for raw_path in sorted(raw_dir.glob("N_Adv_-_*.json")):
        canonical = convert_pcc_source(_load_json(raw_path))
        out_path = out_dir / f"{raw_path.stem}_canonical.json"
        _dump_json(canonical, out_path)
        written.append(out_path)
    return written


def main() -> None:
    for out_path in regenerate_all():
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
