import json
import re
import argparse
from bs4 import BeautifulSoup
import os


def clean_text(raw_text):
    if not raw_text:
        return "UnnamedField"
    text = BeautifulSoup(raw_text, "html.parser").get_text()
    return text.strip().strip(":")


def parse_value_list(value_list_str):
    value_list_str = value_list_str.strip("[] ")
    if not value_list_str:
        return []
    if '=' in value_list_str:
        entries = [entry.strip().lstrip("=") for entry in value_list_str.split(";") if entry.strip()]
    else:
        entries = [entry.strip() for entry in value_list_str.split(";") if entry.strip()]
    return [{"name": entry, "color": "blueLight2"} for entry in entries]


EXTRA_FIELDS = [
    {"name": "Patient", "type": "singleLineText"},
    {"name": "CreatedBy", "type": "singleLineText"},
    {
        "name": "SpeakCare",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Draft", "color": "blueLight2"},
                {"name": "Approved", "color": "greenBright"},
                {"name": "Denied", "color": "redBright"}
            ]
        }
    }
]


MAX_FIELDS_PER_TABLE = 90
FIELD_SPLIT_THRESHOLD = MAX_FIELDS_PER_TABLE - len(EXTRA_FIELDS)


def extract_airtable_fields_from_section(section, prefix):
    section_text = clean_text(section.get("@Text", section.get("@Name", "UnnamedSection")))
    base_section_name = clean_text(section.get("@Name", "UnnamedSection"))
    fields = []
    seen_field_names = set()

    def add_field(field_obj):
        if field_obj["name"] not in seen_field_names:
            fields.append(field_obj)
            seen_field_names.add(field_obj["name"])

    def process_finding(finding, group_hierarchy=[], inherited_result=None):
        text = clean_text(finding.get("@Text", "UnnamedField"))
        name_path = ".".join(group_hierarchy + [finding.get("@Name", "Unnamed")])

        components = finding.get("EntryComponents", {})
        result = components.get("Result", inherited_result) or inherited_result or {}
        style_class = result.get("@StyleClass", "")
        entry_type = result.get("@EntryType", "")

        value = components.get("Value", {})
        notation = components.get("Notation", {})

        field_type = "multilineText"
        options = None

        if style_class == "yn":
            field_type = "singleSelect"
            options = {
                "choices": [
                    {"name": "Yes", "color": "greenBright"},
                    {"name": "No", "color": "redBright"}
                ]
            }
        elif entry_type == "singleCheck":
            field_type = "checkbox"
            options = {"icon": "check", "color": "greenBright"}
        elif entry_type in ("dropDown", "dropDownList") and result.get("@ValueList"):
            field_type = "singleSelect"
            options = {"choices": parse_value_list(result["@ValueList"])}
        elif value.get("@EntryType") in ("dropDown", "dropDownList") and value.get("@ValueList"):
            field_type = "singleSelect"
            options = {"choices": parse_value_list(value["@ValueList"])}
        elif notation.get("@EntryType") in ("dropDown", "dropDownList") and notation.get("@ValueList"):
            field_type = "singleSelect"
            options = {"choices": parse_value_list(notation["@ValueList"])}

        field_obj = {
            "name": name_path + f".{text}",
            "description": text,
            "type": field_type
        }
        if options:
            field_obj["options"] = options

        add_field(field_obj)
        return 1

    def traverse_group(group, group_hierarchy=[], inherited_result=None):
        group_name = group.get("@Name", "")
        if "table" in group_name.lower():
            return [], 0
        element = group.get("Element", {})
        if isinstance(element, list):
            for el in element:
                if el.get("@Type") == "qc.note.FindingTable2":
                    return [], 0
        elif isinstance(element, dict):
            if element.get("@Type") == "qc.note.FindingTable2":
                return [], 0

        group_text = clean_text(group.get("@Text", group_name))
        next_hierarchy = group_hierarchy + [group.get("@Name", group_text)]

        group_result = group.get("EntryComponents", {}).get("Result") or inherited_result or {}

        own_field_count = 0
        findings = group.get("Finding", [])
        if isinstance(findings, dict):
            findings = [findings]

        def deduplicated_choices(findings):
            seen = set()
            unique = []
            for f in findings:
                text = clean_text(f.get("@Text"))
                name = f.get("@Name", "Unnamed")
                label = f"{name}.{text}"
                if label not in seen:
                    unique.append({"name": label, "color": "blueLight2"})
                    seen.add(label)
            return unique

        if group.get("@StyleClass") == "supergroup" and not group.get("EntryComponents"):
            choices = deduplicated_choices(findings)
            if len(choices) > 1:
                full_name = f"{'.'.join(next_hierarchy)}.{group_text}"
                add_field({
                    "name": full_name,
                    "description": group_text,
                    "type": "multipleSelects",
                    "options": {"choices": choices}
                })
                own_field_count += 1
            elif len(choices) == 1:
                label = choices[0]["name"]
                add_field({
                    "name": f"{'.'.join(next_hierarchy)}.{label}",
                    "description": label,
                    "type": "checkbox",
                    "options": {"icon": "check", "color": "greenBright"}
                })
                own_field_count += 1
        elif group_result.get("@EntryType") == "singleCheck" and group_result.get("@StyleClass") == "check" and len(findings) > 0:
            choices = deduplicated_choices(findings)
            for finding in findings:
                result_override = finding.get("EntryComponents", {}).get("Result", {}).get("@EntryType")
                if result_override:
                    own_field_count += process_finding(finding, group_hierarchy=next_hierarchy, inherited_result=group_result)
            if len(choices) > 1:
                full_name = f"{'.'.join(next_hierarchy)}.{group_text}"
                add_field({
                    "name": full_name,
                    "description": group_text,
                    "type": "multipleSelects",
                    "options": {"choices": choices}
                })
                own_field_count += 1
            elif len(choices) == 1:
                label = choices[0]["name"]
                add_field({
                    "name": f"{'.'.join(next_hierarchy)}.{label}",
                    "description": label,
                    "type": "checkbox",
                    "options": {"icon": "check", "color": "greenBright"}
                })
                own_field_count += 1
        elif len(findings) > 1 and not group.get("EntryComponents"):
            choices = deduplicated_choices(findings)
            if len(choices) > 1:
                full_name = f"{'.'.join(next_hierarchy)}.{group_text}"
                add_field({
                    "name": full_name,
                    "description": group_text,
                    "type": "multipleSelects",
                    "options": {"choices": choices}
                })
                own_field_count += 1
            elif len(choices) == 1:
                label = choices[0]["name"]
                add_field({
                    "name": f"{'.'.join(next_hierarchy)}.{label}",
                    "description": label,
                    "type": "checkbox",
                    "options": {"icon": "check", "color": "greenBright"}
                })
                own_field_count += 1
        else:
            for finding in findings:
                own_field_count += process_finding(finding, group_hierarchy=next_hierarchy, inherited_result=group_result)

        if not findings and not group.get("Group") and group.get("@Text"):
            full_name = f"{'.'.join(next_hierarchy)}.{group_text}"
            add_field({
                "name": full_name,
                "description": group_text,
                "type": "multilineText"
            })
            own_field_count += 1

        nested_groups = group.get("Group", [])
        if isinstance(nested_groups, dict):
            nested_groups = [nested_groups]
        for sub_group in nested_groups:
            _, sub_count = traverse_group(sub_group, next_hierarchy, group_result)
            own_field_count += sub_count

        if group.get("FreeText") is not None:
            base_name = clean_text(group["FreeText"].get("@Name") or group_text)
            full_name = f"{'.'.join(next_hierarchy)}.{base_name}"
            add_field({
                "name": full_name,
                "description": group_text,
                "type": "multilineText"
            })
            own_field_count += 1

        return [], own_field_count

    findings = section.get("Finding", [])
    if isinstance(findings, dict):
        findings = [findings]
    for finding in findings:
        process_finding(finding, inherited_result=section.get("EntryComponents", {}).get("Result"))

    groups = section.get("Group", [])
    if isinstance(groups, dict):
        groups = [groups]
    for group in groups:
        traverse_group(group, inherited_result=section.get("EntryComponents", {}).get("Result"))

    if section.get("FreeText") is not None:
        base_name = clean_text(section["FreeText"].get("@Name") or section_text)
        full_name = base_name
        add_field({
            "name": full_name,
            "description": section_text,
            "type": "multilineText"
        })

    if not fields:
        return []

    tables = []
    for i in range(0, len(fields), FIELD_SPLIT_THRESHOLD):
        chunk = fields[i:i + FIELD_SPLIT_THRESHOLD] + EXTRA_FIELDS
        suffix = f"_{i // FIELD_SPLIT_THRESHOLD + 1}" if len(fields) > FIELD_SPLIT_THRESHOLD else ""
        tables.append({
            "name": f"{prefix}.{base_section_name}{suffix}",
            "description": section_text,
            "fields": chunk
        })
    return tables


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert EHR JSON to Airtable table format")
    parser.add_argument("input", help="Path to the input EHR JSON file")
    parser.add_argument("--output-prefix", "-o", required=True, help="Prefix for output JSON files")
    parser.add_argument("--output-dir", "-d", default=".", help="Directory to store output files")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    with open(args.input, "r") as f:
        ehr_data = json.load(f)

    sections = ehr_data["Document"]["Section"]
    if isinstance(sections, dict):
        sections = [sections]

    med_surg_section = next(s for s in sections if s.get("@Name") == "MedSurgNursingAssessmentSection")
    nested_sections = med_surg_section.get("Section", [])
    if isinstance(nested_sections, dict):
        nested_sections = [nested_sections]

    total_fields = 0
    written_sections = 0

    for section in nested_sections:
        tables = extract_airtable_fields_from_section(section, args.output_prefix)
        for table in tables:
            section_filename = os.path.join(args.output_dir, f"{table['name']}.json")
            with open(section_filename, "w") as f:
                json.dump(table, f, indent=2)
            total_fields += len(table["fields"])
            written_sections += 1

    print(f"Converted {written_sections} tables to Airtable format using prefix '{args.output_prefix}'")
    print(f"Total fields extracted: {total_fields}")
