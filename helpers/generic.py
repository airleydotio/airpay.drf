import logging


def pickKeysFromDict(d, keys):
    return {k: d[k] for k in keys if k in d}


def dictHasAnyKeys(d, keys):
    return any(k in d for k in keys)


def keysExistInDict(d, keys):
    return all(k in d for k in keys)


def keysDontExistInDict(d, keys):
    return not any(k in d for k in keys)


def missingKeysInDict(d, keys):
    # also check if value is None if False is
    return [k for k in keys if k not in d or d[k] is None or d[k] == '' or d[k] == [] or d[k] == {}]


def error_logger(e):
    logging.error(e)
