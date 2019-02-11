"""
Methods to interface with Pipfile and requirements*.txt files.
"""
import plette
import viv.types as t
from plette.models import Package


def read_pipfile(fpath) -> plette.Pipfile:
    with open(fpath) as f:
        pipfile = plette.Pipfile.load(f)
    return pipfile


def pip_args_from_pipfile_line(pair: t.Tuple[str, Package]) -> t.List[str]:
    """Takes lines from a Pipfile and translates into args for pip.

    requests = "*" becomes ['requests']
    requests = ">=2.0" becomes ['requests>=2.0']
    requests = {git = "https..." } becomes ['-e', 'https...#egg=requests']
    """
    name, data = pair
    data = data._data
    if data == '*':
        return [name]
    elif isinstance(data, str):
        return [name + data]
    elif isinstance(data, dict):
        if 'git' in data:
            repo = data['git']
            return ['-e', 'git+{repo}#egg={name}'.format(repo=repo, name=name)]
        extras = ''
        if 'extras' in data:
            extras = '[' + ','.join(data['extras']) + ']'
        return ['{name}{extras}{version}'.format(
            name=name,
            extras=extras,
            version=data['version'],
        )]
    else:
        raise ValueError('Could not understand Pipfile config line: ' + str(pair))


def write_requirements_file(packages, fpath: str):
    with open(fpath, 'w') as f:
        requirements = sorted(
            '{name}=={version}'.format(name=d['Name'], version=d['Version'])
            for d in packages.values()
        )
        f.write('\n'.join(requirements))


