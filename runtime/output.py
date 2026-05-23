from __future__ import annotations


def _looks_like_title(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or (stripped.startswith("**") and stripped.endswith("**"))


def format_summary_output(content: str, params_line: str) -> str:
    clean_content = content.strip()
    clean_params = params_line.strip()
    if not clean_content:
        return clean_params

    first_line, separator, rest = clean_content.partition("\n")
    if _looks_like_title(first_line):
        body = rest.lstrip("\n")
        return f"{first_line}\n{clean_params}\n\n{body}" if body else f"{first_line}\n{clean_params}"
    return f"{clean_content}\n\n{clean_params}"
