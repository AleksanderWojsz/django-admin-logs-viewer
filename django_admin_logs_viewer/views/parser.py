import json
import re
from django_admin_logs_viewer.conf import app_settings

def _parse_logs(content, parser_config):
    parser_type = parser_config["type"]
    column_names = list(parser_config.get("column_names", [])) # List, so copy it made
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

    column_names += ["Traceback"]

    return column_names, column_types, rows

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
