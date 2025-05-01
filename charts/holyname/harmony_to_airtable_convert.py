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
                {"name": "Draft", "color": "gray"},
                {"name": "Approved", "color": "greenBright"},
                {"name": "Denied", "color": "redBright"}
            ]
        }
    }
]


MAX_FIELDS_PER_TABLE = 100
FIELD_SPLIT_THRESHOLD = MAX_FIELDS_PER_TABLE - len(EXTRA_FIELDS)


def extract_airtable_fields_from_section(section):
    section_prefix = clean_text(section.get("@Text", section.get("@Name", "UnnamedSection")))
    section_name = clean_text(section.get("@Name", "UnnamedSection"))
    fields = []

    def process_finding(finding, group_hierarchy="", inherited_result=None):
        text = clean_text(finding.get("@Text", "UnnamedField"))
        if not text:
            return 0

        full_name = f"{section_prefix}.{group_hierarchy}.{text}" if group_hierarchy else f"{section_prefix}.{text}"

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
            "name": full_name,
            "description": text,
            "type": field_type
        }
        if options:
            field_obj["options"] = options

        fields.append(field_obj)
        return 1

    def traverse_group(group, group_hierarchy="", inherited_result=None):
        group_text = clean_text(group.get("@Text", group.get("@Name", "")))
        next_hierarchy = f"{group_hierarchy}.{group_text}" if group_hierarchy else group_text

        group_result = group.get("EntryComponents", {}).get("Result") or inherited_result or {}

        own_field_count = 0
        findings = group.get("Finding", [])
        if isinstance(findings, dict):
            findings = [findings]

        if group.get("@StyleClass") == "supergroup" and not group.get("EntryComponents"):
            choices = [
                {"name": clean_text(f.get("@Text")), "color": "blueLight2"}
                for f in findings if clean_text(f.get("@Text"))
            ]
            if choices:
                full_name = f"{section_prefix}.{group_hierarchy}.{group_text}" if group_hierarchy else f"{section_prefix}.{group_text}"
                fields.append({
                    "name": full_name,
                    "description": group_text,
                    "type": "multipleSelects",
                    "options": {"choices": choices}
                })
                own_field_count += 1
        elif group_result.get("@EntryType") == "singleCheck" and group_result.get("@StyleClass") == "check" and len(findings) > 0:
            bundled_choices = []
            for finding in findings:
                result_override = finding.get("EntryComponents", {}).get("Result", {}).get("@EntryType")
                if result_override:
                    own_field_count += process_finding(finding, group_hierarchy=next_hierarchy, inherited_result=group_result)
                else:
                    text = clean_text(finding.get("@Text"))
                    if text:
                        bundled_choices.append({"name": text, "color": "blueLight2"})
            if len(bundled_choices) > 1:
                fields.append({
                    "name": f"{section_prefix}.{next_hierarchy}",
                    "description": group_text,
                    "type": "multipleSelects",
                    "options": {"choices": bundled_choices}
                })
                own_field_count += 1
            elif len(bundled_choices) == 1:
                fields.append({
                    "name": f"{section_prefix}.{next_hierarchy}.{bundled_choices[0]['name']}",
                    "description": bundled_choices[0]['name'],
                    "type": "checkbox",
                    "options": {"icon": "check", "color": "greenBright"}
                })
                own_field_count += 1
        elif len(findings) > 1 and not group.get("EntryComponents"):
            choices = [
                {"name": clean_text(f.get("@Text")), "color": "blueLight2"}
                for f in findings if clean_text(f.get("@Text"))
            ]
            if choices:
                fields.append({
                    "name": f"{section_prefix}.{next_hierarchy}",
                    "description": group_text,
                    "type": "multipleSelects",
                    "options": {"choices": choices}
                })
                own_field_count += 1
        else:
            for finding in findings:
                own_field_count += process_finding(finding, group_hierarchy=next_hierarchy, inherited_result=group_result)

        if not findings and not group.get("Group"):
            fields.append({
                "name": f"{section_prefix}.{next_hierarchy}",
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
            fields.append({
                "name": f"{section_prefix}.{group_hierarchy}.{base_name}" if group_hierarchy else f"{section_prefix}.{base_name}",
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
        base_name = clean_text(section["FreeText"].get("@Name") or section_prefix)
        fields.append({
            "name": base_name,
            "description": section_prefix,
            "type": "multilineText"
        })

    if not fields:
        return []

    tables = []
    for i in range(0, len(fields), FIELD_SPLIT_THRESHOLD):
        chunk = fields[i:i + FIELD_SPLIT_THRESHOLD] + EXTRA_FIELDS
        tables.append({
            "name": section_name,
            "description": section_prefix,
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
        tables = extract_airtable_fields_from_section(section)
        for idx, table in enumerate(tables):
            suffix = f"_{idx+1}" if len(tables) > 1 else ""
            section_filename = os.path.join(args.output_dir, f"{args.output_prefix}.{table['name']}{suffix}.json")
            with open(section_filename, "w") as f:
                json.dump(table, f, indent=2)
            total_fields += len(table["fields"])
            written_sections += 1

    print(f"Converted {written_sections} tables to Airtable format using prefix '{args.output_prefix}'")
    print(f"Total fields extracted: {total_fields}")
