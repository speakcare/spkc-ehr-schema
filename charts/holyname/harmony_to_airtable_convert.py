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


def extract_airtable_fields_from_section(section):
    section_prefix = clean_text(section.get("@Text", section.get("@Name", "UnnamedSection")))
    section_name = clean_text(section.get("@Name", "UnnamedSection"))
    fields = []
    group_logs = []

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

    def handle_supergroup(group, group_hierarchy):
        finding_array = group.get("Finding", [])
        if isinstance(finding_array, dict):
            finding_array = [finding_array]

        choices = []
        for finding in finding_array:
            text = clean_text(finding.get("@Text"))
            if text:
                choices.append({"name": text, "color": "blueLight2"})

        group_text = clean_text(group.get("@Text", group.get("@Name", "")))
        full_name = f"{section_prefix}.{group_hierarchy}.{group_text}" if group_hierarchy else f"{section_prefix}.{group_text}"

        fields.append({
            "name": full_name,
            "description": group_text,
            "type": "multipleSelects",
            "options": {
                "choices": choices
            }
        })
        return 1

    def traverse_group(group, group_hierarchy="", inherited_result=None, depth=1):
        group_text = clean_text(group.get("@Text", group.get("@Name", "")))
        next_hierarchy = f"{group_hierarchy}.{group_text}" if group_hierarchy else group_text

        group_result = group.get("EntryComponents", {}).get("Result")
        if group_result is None:
            group_result = inherited_result or {}

        own_field_count = 0
        logs = []

        is_supergroup = group.get("@StyleClass") == "supergroup"
        has_entry_components = bool(group.get("EntryComponents"))

        findings = group.get("Finding", [])
        if isinstance(findings, dict):
            findings = [findings]

        if is_supergroup and not has_entry_components:
            own_field_count += handle_supergroup(group, group_hierarchy)
        elif group_result.get("@EntryType") == "singleCheck" and group_result.get("@StyleClass") == "check" and len(findings) > 0:
            bundled_choices = []
            field_count = 0
            for finding in findings:
                result_override = finding.get("EntryComponents", {}).get("Result", {}).get("@EntryType")
                if result_override:
                    field_count += process_finding(finding, group_hierarchy=next_hierarchy, inherited_result=group_result)
                else:
                    text = clean_text(finding.get("@Text"))
                    if text:
                        bundled_choices.append({"name": text, "color": "blueLight2"})

            if len(bundled_choices) > 1:
                full_name = f"{section_prefix}.{next_hierarchy}"
                fields.append({
                    "name": full_name,
                    "description": group_text,
                    "type": "multipleSelects",
                    "options": {"choices": bundled_choices}
                })
                field_count += 1
            elif len(bundled_choices) == 1:
                fields.append({
                    "name": f"{section_prefix}.{next_hierarchy}.{bundled_choices[0]['name']}",
                    "description": bundled_choices[0]['name'],
                    "type": "checkbox",
                    "options": {"icon": "check", "color": "greenBright"}
                })
                field_count += 1
            own_field_count += field_count
        elif len(findings) > 1 and not has_entry_components:
            choices = []
            for finding in findings:
                text = clean_text(finding.get("@Text"))
                if text:
                    choices.append({"name": text, "color": "blueLight2"})
            if choices:
                full_name = f"{section_prefix}.{next_hierarchy}"
                fields.append({
                    "name": full_name,
                    "description": group_text,
                    "type": "multipleSelects",
                    "options": {"choices": choices}
                })
                own_field_count += 1
        else:
            for finding in findings:
                own_field_count += process_finding(finding, group_hierarchy=next_hierarchy, inherited_result=group_result)

        nested_groups = group.get("Group", [])
        if isinstance(nested_groups, dict):
            nested_groups = [nested_groups]

        total_field_count = own_field_count
        if not findings and not nested_groups:
            full_name = f"{section_prefix}.{next_hierarchy}"
            fields.append({
                "name": full_name,
                "description": group_text,
                "type": "multilineText"
            })
            own_field_count += 1
            total_field_count += 1

        for sub_group in nested_groups:
            child_logs, child_total = traverse_group(sub_group, next_hierarchy, group_result, depth + 1)
            logs.extend(child_logs)
            total_field_count += child_total

        if group.get("FreeText") is not None:
            base_name = clean_text(group.get("FreeText", {}).get("@Name")) if group.get("FreeText", {}).get("@Name") else group_text
            full_name = f"{section_prefix}.{group_hierarchy}.{base_name}" if group_hierarchy else f"{section_prefix}.{base_name}"
            fields.append({
                "name": full_name,
                "description": group_text,
                "type": "multilineText"
            })
            own_field_count += 1
            total_field_count += 1

        logs.insert(0, (depth, group_text, own_field_count, total_field_count))
        return logs, total_field_count

    total_own_field_count = 0
    findings = section.get("Finding", [])
    if isinstance(findings, dict):
        findings = [findings]
    for finding in findings:
        total_own_field_count += process_finding(finding, group_hierarchy="", inherited_result=section.get("EntryComponents", {}).get("Result"))

    total_field_count = total_own_field_count
    groups = section.get("Group", [])
    if isinstance(groups, dict):
        groups = [groups]

    if section.get("FreeText") is not None:
        base_name = clean_text(section.get("FreeText", {}).get("@Name")) if section.get("FreeText", {}).get("@Name") else section_prefix
        fields.append({
            "name": base_name,
            "description": section_prefix,
            "type": "multilineText"
        })
        total_own_field_count += 1
        total_field_count += 1

    for group in groups:
        logs, group_total = traverse_group(group, group_hierarchy="", inherited_result=section.get("EntryComponents", {}).get("Result"), depth=1)
        group_logs.extend(logs)
        total_field_count += group_total

    if total_field_count == 0:
        return None, 0

    print(f"Section '{section_name}': fields ({total_own_field_count}, {total_field_count})")
    for depth, group_text, own, total in group_logs:
        indent = "---+" * depth
        print(f"{indent} Group: {group_text} (fields {own}, {total})")
    print(f"Total fields: {len(fields)}\n")

    fields.extend([
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
    ])

    return {
        "name": section_name,
        "description": section_prefix,
        "fields": fields
    }, len(fields)


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
        table, field_count = extract_airtable_fields_from_section(section)
        if table:
            section_filename = os.path.join(args.output_dir, f"{args.output_prefix}.{table['name']}.json")
            with open(section_filename, "w") as f:
                json.dump(table, f, indent=2)
            total_fields += field_count
            written_sections += 1

    print(f"Converted {written_sections} sections to Airtable format using prefix '{args.output_prefix}'")
    print(f"Total fields extracted: {total_fields}")
