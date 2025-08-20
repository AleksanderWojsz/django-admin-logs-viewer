---
sidebar_position: 3
hide_table_of_contents: false
---

# Configuration

:::warning
For each step to work, complete all the previous ones.
:::

**In `settings.py`:**

### 1. Set path to your logs directories and/or logs files. Example:
```python
import os

LOGS_DIRS = [
    os.path.join(BASE_DIR, "logs"),
    os.path.join(BASE_DIR, "some_other_logs_directory/commands/logfile_commands.log"),
]
```

*Result:* 
<img src={require('./imgs/img_1.png').default}/>

- Not parsed file is displayed:
<img src={require('./imgs/img_2.png').default}/>

### 2. Set logs separator using regex:

```python
LOGS_SEPARATORS = [
    r'^\{', # (This one matches line starting with `{`)
    # More can be added. If any matches, line will be split.
]

LOGS_ROWS_PER_PAGE = 50 # Optional. Default: 100
```

*Result:*
- Rows are separated. Search is enabled:
<img src={require('./imgs/img_3.png').default}/>
<img src={require('./imgs/img_4.png').default}/>

### 3. Set one of parser objects:

There are three row parsing options:
- a) Split columns by separator
```python
LOGS_PARSER = {
    "type": "separator", # Required
    "separator": "|", # Required
    "column_names": ["Level", "Time", "Path", "File & Line No ", "Message"], # Optional
    "column_types": ["LEVEL", "TIME", "OTHER", "OTHER", "OTHER"], # Optional
}
```

- b) Parse as JSON objects
```python
LOGS_PARSER = {
    "type": "json", # Required
    "column_names": ["Level", "Time", "Path", "File & Line No ", "Message"], # Optional. If not specified, keys from JSON object are used
    "column_types": ["LEVEL", "TIME", "OTHER", "OTHER", "OTHER"], # Optional
}
```

- c) Split columns by regex groups
```python
LOGS_PARSER = {
    "type": "regex", # Required
    "pattern": r'\{\s*"level"\s*:\s*"([^"]+)"\s*,\s*"datetime"\s*:\s*"([^"]+)"\s*,\s*"source"\s*:\s*"([^"]+)"\s*,\s*"file"\s*:\s*"([^"]+)"\s*,\s*"message"\s*:\s*"([^"]+)"\s*\}', # Required (this one matches json)
    "column_names": ["Level", "Time", "Path", "File & Line No ", "Message"], # Optional
    "column_types": ["LEVEL", "TIME", "OTHER", "OTHER", "OTHER"], # Optional
}
```

:::note
`column_names` are optional.  
`column_types` allows for level and time filtering and colors. Keywords are `"LEVEL"`, `"TIME"`.
:::

*Result:*
<img src={require('./imgs/img_5.png').default}/>

### 4. Show errors since last log in:

Both of these are required:
```python
SHOW_ERRORS_SINCE_LAST_LOG_IN = True # Default: False. Assumes logs are ordered from older to newer. Can affect performance for large files.
LOGS_TIMEZONE = "Europe/Warsaw"
```

*Result:*
<img src={require('./imgs/img_6.png').default}/>
