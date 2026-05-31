# PCC source-template converter — plan

## Background

`assmnt_templates/N_Adv_-_*.json` files in this repo are the **materialized** form
of PCC templates: every per-slot question is enumerated explicitly. Skin alone has
~4,215 questions across 40 wound slots; the whole N Adv - Skilled Evaluation is
~5,334 questions.

We have an alternative source: the **PCC raw template export** (the JSON behind
PCC's edit-template page). In the raw form, each clinical concept is written
once. The 40 wound slots come from a single `imageMap` widget with
`maxIssues: 40`; everything inside `imageMap.imageMapControls.composition` is the
per-slot field definition, written once.

This converter takes the raw form and produces a canonical JSON that's
structurally faithful to the source — one question per source widget — with
repeated-slot concepts represented as a single `repeatedQuestionGroup` carrying
`slotKind` and `slotCount`.

## Two-pass split (only pass 1 is in scope here)

1. **Structural converter** (this PR, `n_adv_questions.py`)
   Pure walk of the raw template. One question per leaf input widget. ImageMaps
   become `repeatedQuestionGroup`s. No regrouping decisions, no clinical-model
   choices. Output is mechanically derivable from the source.

2. **Grouping pass** (future PR, `n_adv_groupings.py`)
   Takes the canonical JSON plus an HTML-derived grouping spec (scraped from the
   PCC UI by a separate tool) and adds a `visualGroup` tag to questions that
   share a visual heading like "Mobility Devices" or "Vision Aids". May also
   rewrite contiguous "ams"-style boolean siblings into synthetic multi-select
   questions. The grouping decisions need the HTML render — they aren't reliable
   from the source JSON alone (see "Why grouping is deferred" below).

## In scope (this PR)

### Files

```
src/pcc_schema/
  n_adv_templates/                                # NEW — raw PCC source files
    N_Adv_-_Skilled_Evaluation.json
    N_Adv_-_Clinical_Admission.json
  n_adv_questions.py                              # NEW — converter
  assmnt_templates/
    N_Adv_-_Skilled_Evaluation_canonical.json     # NEW — generated output
    N_Adv_-_Clinical_Admission_canonical.json     # NEW — generated output
tests/
  test_n_adv_questions.py                         # NEW
```

The existing `assmnt_templates/N_Adv_-_Skilled_Evaluation.json` and
`assmnt_templates/N_Adv_-_Clinical_Admission.json` (the materialized form) stay
untouched. Consumers opt in to the canonical form by filename.

### Output envelope

```jsonc
{
  "templateId": "<source.templateId>",         // uuid (raw source is uuid, not int)
  "templateName": "<source.name>",
  "templateVersion": "<source.version>",
  "sections": [
    {
      "sectionDescription": "Vitals",
      "sectionSequence": 1,
      "assessmentQuestionGroups": [
        { "groupNumber": "1", "groupTitle": "...", "questions": [...] }
      ],
      "repeatedQuestionGroups": []               // empty for non-repeating sections
    },
    {
      "sectionDescription": "Skin",
      "sectionSequence": 12,
      "assessmentQuestionGroups": [...],         // anything outside the imageMap
      "repeatedQuestionGroups": [
        {
          "slotKind": "Skin Issues",             // de.name
          "slotCount": 40,                       // imageMap.maxIssues
          "dataElementId": "cd56b26c-...",
          "imageMapId": "63581fe9-...",
          "questions": [                         // ~104 per-slot questions, each ONCE
            { "questionKey": "53880636-...", "questionText": "Location", ... }
          ]
        }
      ]
    }
  ]
}
```

### Per-question shape

```jsonc
{
  "questionKey":    "<widget.id>",              // UUID of the leaf widget
  "dataElementId":  "<parent de.dataElementId>",
  "questionText":   "<widget.label || widget.name>",
  "widgetType":     "checkbox|radio|select|textbox|date",
  "required":       false,
  "responseOptions": [
    { "responseText": "<opt.text>", "responseValue": "<opt.value>" }
  ],
  "isAutoPopulated":    false,                  // true if any template rule autoPopulates this widget
  "sourceQuestionKeys": []                      // widget ids that drive the autoPopulate (sorted, deduped)
}
```

Notes:
- `questionKey` is the widget's own `id`, not the parent `dataElementId`
  (verified against existing materialized files: `1fc078f7-...` for "Heart Rate
  Character" is the inner `select` id, not the wrapper).
- `widgetType` preserves the source's type verbatim. We are NOT mapping to PCC's
  short codes (`rad`, `chk`, `mtxt`, `temp`, ...) — that mapping is lossy and
  unnecessary for the canonical form.
- `sourceQuestionKeys` is a **list** (not a single key) because the template
  can have multiple rules targeting the same widget, each conditioned on a
  different source. Skilled Eval has 12 multi-source autoPopulate targets;
  one has 6 distinct sources. Singular naming would lose information.

### AutoPopulate handling

PCC templates use `rule.action[].name == "autoPopulate"` rules to derive
questions from other user-entered questions. The MDS section in N Adv -
Skilled Evaluation is **entirely** autopopulated (47/47 widgets are targets of
autoPopulate rules), which is why PCC's UI hides it — there's nothing for a
nurse to fill in. The materialized JSON still includes MDS because PCC's API
exports everything.

The converter handles this by:

1. **Building an autoPopulate index** from the template's top-level `rules`
   array. For every rule whose `action[].name == "autoPopulate"`:
   - target widget id = `action[].path`
   - source widget ids = every `condition.path` found anywhere in
     `rule.conditions` (recursive — conditions nest under
     `conditionOrConditions` and may also nest inside `logic: "and"/"or"`
     wrappers).

2. **Annotating each question** with `isAutoPopulated` and
   `sourceQuestionKeys` based on the index.

3. **Dropping a section entirely** if it has at least one question and
   every question (assessment + repeated) is autopopulated. Section sequence
   numbers are reassigned to stay contiguous after drops.

Skilled Evaluation result: MDS section dropped (47 questions removed); 5
remaining autopopulated questions across other sections stay but are tagged.

### Algorithm

```
convert_pcc_source(source):
  de_index = {de.dataElementId: de for de in source.usedDataElements.dataElements}
  return {
    templateId, templateName, templateVersion,
    sections: [walk_section(s, i) for i, s in enumerate(source.sections)]
  }

walk_section(section, idx):
  assessment_groups = []
  repeated_groups = []
  for group in section.groups:
    questions, repeats = walk_contents(group.contents)
    if questions:
      assessment_groups.append({groupNumber, groupTitle, questions})
    repeated_groups.extend(repeats)
  return {sectionDescription, sectionSequence, assessmentQuestionGroups, repeatedQuestionGroups}

walk_contents(contents) -> (questions, repeats):
  for content in contents:
    if content.type == "dataElement":
      if content.refDataElementId is None:    # heading — skip (used by grouping pass)
        continue
      de = de_index[content.refDataElementId]
      yield from walk_composition(de.composition, parent_de=de)
    elif content.type == "dataElementLayout":
      yield from walk_contents(content.dataElements)

walk_composition(composition, parent_de) -> (questions, repeats):
  for entry in composition:
    if entry.type == "imageMap":
      slot_questions, _ = walk_composition(
        entry.imageMapControls.composition, parent_de=parent_de
      )
      yield as repeat: {
        slotKind: parent_de.name,
        slotCount: entry.maxIssues,
        dataElementId: parent_de.dataElementId,
        imageMapId: entry.id,
        questions: slot_questions,
      }
    elif entry.type in {"checkbox", "radio", "select", "textbox", "date"}:
      yield as question: {
        questionKey: entry.id,
        dataElementId: parent_de.dataElementId,
        questionText: entry.label or entry.name,
        widgetType: entry.type,
        required: entry.required or False,
        responseOptions: [
          {responseText: o.text, responseValue: o.value} for o in (entry.options or [])
        ],
      }
    elif entry.type in {"container", "imageMapControlsSection"}:
      yield from walk_composition(entry.composition, parent_de)
    # ignore: var, rule, narrative, refControl, instruction, mediaFile, api,
    #         imageMapAreaCircle, imageMapAreaGroup, controlValueIdentifier,
    #         instanceIdentifier, controlExternalData
```

### Tests (`tests/test_n_adv_questions.py`)

Run against both committed raw templates:

1. **Skin → 1 repeatedQuestionGroup** with `slotKind="Skin Issues"`,
   `slotCount=40`, and ~104 per-slot questions.
2. **All 4 imageMaps** detected per template with correct `maxIssues`:
   Skin=40, Lung=30, Pain=10, Edema=10.
3. **Body Temperature → 2 questions** in Vitals (textbox + select), not 1.
4. **Hearing Aid(s) - Care Profile → 3 questions** (3 inner checkboxes flattened).
5. **Mobility Devices area → 6 sibling questions** in Functional group
   (Cane/Crutch, Walker, Electric Wheelchair, Manual Wheelchair, Limb
   Prosthesis, Other mobility device). NOT collapsed — collapsing is grouping
   pass's job.
6. **Section names + order** match the raw source's sections.
7. **questionKey is the widget id, not the dataElementId.** Spot-checked on
   Heart Rate Character (`1fc078f7-...`).
8. **Total leaf question count**: ~547 for Skilled Evaluation (594 - 47
   dropped from MDS section), ~588 for Clinical Admission minus whatever its
   100%-autopopulated sections turn out to be. Materialized files have
   ~5,334 / 5,369.
9. **MDS section dropped from Skilled Evaluation canonical** (100%
   autopopulated). Section list does not contain "MDS".
10. **At least one autopopulated question outside MDS** carries
    `isAutoPopulated: true` and a non-empty `sourceQuestionKeys`.

### Acceptance criteria

- `pytest tests/test_n_adv_questions.py` passes.
- `python -m pcc_schema.n_adv_questions` (or equivalent CLI) regenerates both
  canonical JSONs from the raw source files, with byte-stable output across runs.
- Generated canonical JSONs are committed alongside the raw sources.

## Out of scope (deferred)

- **Grouping pass** — `visualGroup` tags, multi-select collapse of contiguous
  "ams"-style booleans (Mobility Devices, Vision Aids, Therapy, etc.). Needs
  HTML-derived grouping spec.
- **PCC questionType code mapping** — the existing materialized files use short
  codes like `rad`, `chk`, `temp`, `ams`, `mcsh`. The canonical form preserves
  the raw widget type (`radio`, `checkbox`, `textbox`, ...) instead. Mapping to
  PCC codes is lossy (Body Temperature → "temp" bundles two widgets) and only
  needed if downstream code requires it.
- **Wiring into `export_pcc_schemas.py`** — the existing pipeline keeps
  producing materialized JSONs; canonical JSONs are produced by the new
  converter independently. Reconciling the two flows is a follow-up.
- **Consumers** in `spkc-chart-mapping` / KB / med-charting that need to learn
  about `repeatedQuestionGroups`. Each will land in its own branch in its own
  repo.

## Why grouping is deferred (rationale)

The user proposed collapsing visually-grouped boolean siblings (e.g. "Mobility
Devices" → one multi-select with [Cane/Crutch, Walker, ...]) into synthetic
multi-selects so the LLM gets cleaner context. This is the right end state.

Initial structural detection rule attempted: "heading dataElement (no
refDataElementId) + contiguous run of siblings whose composition is
`[checkbox, no options]`". This works for ~70% of `questionType=="ams"` items
but breaks on:

- **Hearing Aid(s) - Care Profile**: composition is `[checkbox, checkbox,
  checkbox, rule, rule]` (3 sub-flags, not 1).
- **Nebulizer Therapy - Care Profile**: composition is `[checkbox, radio, rule,
  rule]` — the radio is a follow-up revealed when the checkbox is checked.
- **Bladder (Foley) Catheter - Care Profile**: same pattern, checkbox +
  follow-up radio.

The follow-up widgets and the visual reveal logic are encoded in `rule` entries
that reference opaque widget IDs — interpreting them to recover visual hierarchy
is fragile.

The HTML render of the PCC template carries the visual grouping cleanly
(headings, indented checkbox runs, conditional-reveal sections). The grouping
pass will consume an HTML-derived spec produced by a separate scraping tool that
the user is building. Keeping the converter HTML-free means it ships independently
and doesn't block on the scraper.

## Execution order

1. Create branch off `main`: `pcc-source-converter`. ✅
2. Write `plan.md`. ✅
3. Copy raw PCC source JSONs from `~/Downloads/` to
   `src/pcc_schema/n_adv_templates/`.
4. Write `n_adv_questions.py` skeleton + tests 1-3 (imageMap + Vitals
   structural), run, eyeball output for Vitals section.
5. Add full algorithm + remaining tests, run on both templates, write canonical
   JSONs to `assmnt_templates/`.
6. Show generated canonical JSON for one section (likely Skin) to confirm shape
   before committing.

Confirm at the end of each step before moving on.
