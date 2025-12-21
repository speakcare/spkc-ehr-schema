import csv
import os
from typing import Dict, Literal, TextIO, Optional
from contextlib import closing
import io

from .sanitize_text import sanitize_for_json

DuplicatePolicy = Literal["last", "first", "error", "concat"]

def read_key_value_csv_stream(
    stream: TextIO,
    key_col: str,
    value_col: str,
    *,
    case_insensitive: bool = False,
    on_duplicate: DuplicatePolicy = "last",
    skip_blank_keys: bool = True,
    strip_whitespace: bool = True,
    concat_sep: str = ". ",
    key_prefix: Optional[str] = None,
    sanitize_values: bool = True,
    skip_first_row: bool = False,
) -> Dict[str, str]:
    """
    Build a dict from two specific columns in a CSV, reading from a TEXT stream.

    Note: The stream must yield text (not bytes). For bytes (e.g., S3 StreamingBody),
    wrap with io.TextIOWrapper(..., encoding="utf-8-sig", newline="").

    Args:
        stream: Text stream positioned at the start of a CSV with a header row.
        key_col: Column name to use for dictionary keys.
        value_col: Column name to use for dictionary values.
        case_insensitive: If True, match headers case-insensitively.
        on_duplicate:
            - "last"   : last value wins (default)
            - "first"  : first value wins
            - "error"  : raise on duplicate key
            - "concat" : concatenate values using `concat_sep`
        skip_blank_keys: If True, ignore rows where key is empty/only spaces.
        strip_whitespace: If True, strip leading/trailing whitespace from keys/values.
        concat_sep: Separator used when on_duplicate="concat" (default: ". ").
        key_prefix: If provided, prefix keys with "{key_prefix}_" unless already prefixed.
        sanitize_values: If True, sanitize values by removing HTML tags and JSON-breaking characters.

    Returns:
        dict mapping keys -> single string values
    """
    result: Dict[str, str] = {}

    # csv module recommendation: pass newline="" to the *file open* call;
    # here we assume the caller opened the stream correctly.
    reader = csv.DictReader(stream)
    if reader.fieldnames is None:
        raise ValueError("CSV appears to have no header row.")
    headers = reader.fieldnames

    def find_header(name: str) -> str:
        if not case_insensitive:
            if name in headers:
                return name
            raise KeyError(f"Column '{name}' not found. Available: {headers}")
        lower_map = {h.lower(): h for h in headers}
        actual = lower_map.get(name.lower())
        if actual is None:
            raise KeyError(f"Column '{name}' (case-insensitive) not found. Available: {headers}")
        return actual

    key_h = find_header(key_col)
    val_h = find_header(value_col)

    for line_no, row in enumerate(reader, start=2):  # header is line 1
        k = row.get(key_h, "")
        v = row.get(val_h, "")
        if strip_whitespace:
            k = (k or "").strip()
            v = (v or "").strip()

        if skip_blank_keys and not k:
            continue

        # Apply key prefix if specified
        if key_prefix is not None:
            prefix_with_underscore = f"{key_prefix}_"
            if not k.startswith(prefix_with_underscore):
                k = f"{prefix_with_underscore}{k}"

        # Sanitize value if requested
        if sanitize_values:
            v = sanitize_for_json(v)

        if on_duplicate == "last":
            result[k] = v
        elif on_duplicate == "first":
            if k not in result:
                result[k] = v
        elif on_duplicate == "error":
            if k in result:
                raise ValueError(f"Duplicate key '{k}' on CSV line {line_no}.")
            result[k] = v
        elif on_duplicate == "concat":
            if k not in result or not result[k]:
                result[k] = v
            else:
                result[k] = f"{result[k]}{concat_sep}{v}"
        else:
            raise ValueError(f"Unknown on_duplicate policy: {on_duplicate}")

    return result


# ----------------- Convenience wrappers -----------------

def read_key_value_csv_path(
    path: str,
    key_col: str,
    value_col: str,
    **kwargs
) -> Dict[str, str]:
    """
    Open a *local file* and delegate to read_key_value_csv_stream.
    Uses encoding='utf-8-sig' to gracefully handle BOM and newline='' as recommended by csv.
    """
    with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
        return read_key_value_csv_stream(f, key_col, value_col, **kwargs)


def read_key_value_csv_s3(
    bucket: str,
    key: str,
    key_col: str,
    value_col: str,
    *,
    s3_client: Optional[object] = None,
    **kwargs
) -> Dict[str, str]:
    """
    Fetch a CSV from S3 and delegate to read_key_value_csv_stream.
    Wraps the StreamingBody (bytes) in a TextIOWrapper with utf-8-sig handling.
    """
    import boto3  # Available by default in AWS Lambda; add to your container if needed
    import os  # Import os for environment variable access

    s3 = s3_client or boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    # Decode bytes → text; handle BOM; set newline="" for csv correctness
    text_stream = io.TextIOWrapper(obj["Body"], encoding="utf-8-sig", newline="")
    # Ensure wrapper gets closed (also closes underlying StreamingBody when GC'd)
    with closing(text_stream) as f:
        return read_key_value_csv_stream(f, key_col, value_col, **kwargs)
