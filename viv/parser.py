import plette


def read_pipfile(fpath) -> plette.Pipfile:
    with open(fpath) as f:
        pipfile = plette.Pipfile.load(f)
    return pipfile
