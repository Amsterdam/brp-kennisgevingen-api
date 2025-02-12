def preprocessing_filter_spec(endpoints):
    filtered = []
    for path, path_regex, method, callbacks in endpoints:
        if not path.startswith("/openapi."):
            filtered.append((path, path_regex, method, callbacks))
    return filtered
