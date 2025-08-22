import re
from enum import Enum
from django_admin_logs_viewer.conf import app_settings

class LOGS_PREDEFINED_REGEXES:
    # JSON style log: {"level":"INFO","time":"2025-08-22T12:34:56","path":"/app","file":"app.py","message":"Something happened"}
    json = r'^\{\s*"level"\s*:\s*"([^"]+)"\s*,\s*"datetime"\s*:\s*"([^"]+)"\s*,\s*"source"\s*:\s*"([^"]+)"\s*,\s*"file"\s*:\s*"([^"]+)"\s*,\s*"message"\s*:\s*"([^"]+)"\s*\}$'

    # Comma-separated: Level,Time,Path,File,Message
    comma_separated = r'^(.*?),(.*?),(.*?),(.*?),(.*)$'

    # Space-separated simple log: [LEVEL] 2025-08-22T12:34:56 Message
    simple_space = r'^\[(\w+)\]\s+(\S+)\s+(.*)$'

    # Syslog format: Aug 22 12:34:56 hostname program[pid]: message
    syslog = r'^(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(\S+)\[(\d+)\]:\s+(.*)$'

class ParseMode(Enum):
    RAW_CONTENT = "raw_content"
    ROWS_AND_COLUMNS = "rows_and_columns"

def _get_parser_config(name):
    user_parsers = getattr(app_settings, "LOGS_PARSERS", {})
    if name in user_parsers:
        return user_parsers[name]
    raise ValueError(f"Parser '{name}' not found in LOGS_PARSERS.")

def _parse_logs(content, parser_name):
    if not parser_name:
        return ParseMode.RAW_CONTENT, None, None, None, None

    parser_config = _get_parser_config(parser_name)
    column_names = list(parser_config.get("column_names", [])) # copy
    column_types = parser_config.get("column_types", [])
    pattern = parser_config["pattern"]
    datetime_format = parser_config.get("datetime_format")

    regex = re.compile(pattern)
    rows = []
    current_row = None

    for line in content.splitlines():
        match = regex.match(line)
        if match:
            if current_row:
                rows.append(current_row)
            values = list(match.groups())
            values.append("") # Traceback
            current_row = values
        else:
            if current_row:
                current_row[-1] += ("\n" if current_row[-1] else "") + line
            else:
                rows.append([f"Unmatched line: {line}"])

    if current_row:
        rows.append(current_row)

    if column_names:
        column_names += ["Traceback"]

    return ParseMode.ROWS_AND_COLUMNS, column_names, column_types, rows, datetime_format
