import re


def preprocessing_filter_spec(endpoints):
    filtered = []
    for path, path_regex, method, callbacks in endpoints:
        if not re.match(r"(.+v1$)|(.+/openapi)", path):
            filtered.append((path, path_regex, method, callbacks))
    return filtered
