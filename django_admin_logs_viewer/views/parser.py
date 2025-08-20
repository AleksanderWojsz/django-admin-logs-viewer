import json
import re
from enum import Enum
from django_admin_logs_viewer.conf import app_settings

class ParseMode(Enum):
    RAW_CONTENT = "raw_content"
    ROWS = "rows"
    ROWS_AND_COLUMNS = "rows_and_columns"

def _parse_logs(content, parser_config):
   # No separators, no parser -> show raw file
    if not parser_config and not app_settings.LOGS_SEPARATORS:
        return ParseMode.RAW_CONTENT, None, None, None

   # Separators, no parser -> list of rows (single column)
    if not parser_config and app_settings.LOGS_SEPARATORS:
        records = _split_log_records(content, app_settings.LOGS_SEPARATORS)
        return ParseMode.ROWS, None, None, [[r] for r in records]

    parser_type = parser_config["type"]
    column_names = list(parser_config.get("column_names", [])) # copy
    column_types = parser_config.get("column_types", [])
    separators = app_settings.LOGS_SEPARATORS

    records = _split_log_records(content, separators)
    rows = []

    for record in records:
        try:
            main_line, *traceback_text = record.split("\n", maxsplit=1)

            if parser_type == "separator":
                values = main_line.split(parser_config["separator"])
            elif parser_type == "json":
                main_line = main_line.replace("\\", "\\\\") # So `\` is parsed correctly
                obj = json.loads(main_line)
                if not column_names:
                    column_names = list(obj.keys())
                values = list(obj.values())
            else: # parser_type == "regex":
                match = re.fullmatch(parser_config["pattern"], main_line)
                if not match:
                    raise ValueError(f"Regex did not match line: {main_line}")
                values = list(match.groups())

            if traceback_text:
                values.append(traceback_text[0])
            else:
                values.append("")

            rows.append(values)

        except Exception as e:
            rows.append([f"Parse error: {e}", record])

    if column_names:
        column_names += ["Traceback"]
    return ParseMode.ROWS_AND_COLUMNS, column_names, column_types, rows

def _split_log_records(content, separators):
    separator_pattern = re.compile("|".join(separators), re.MULTILINE)

    records = []
    current_record = [] # Can be multiline
    for line in content.splitlines():
        if separator_pattern.match(line) and current_record:
            records.append("\n".join(current_record))
            current_record = [line]
        else:
            current_record.append(line)

    if current_record:
        records.append("\n".join(current_record))

    return records
