import os
import sys
import re
import shutil
import viv.types as t
from viv.parser import read_pipfile
from os import path
from email.parser import HeaderParser
import subprocess as sub


def norm_package_name(s: str) -> str:
    """Eliminate casing and -/_ discrepancies from package names."""
    return s.lower().replace('-', '_')


def _resolve_pip_command() -> t.Opt[str]:
    """Find the pip command for the env. Prefer using resolve_pip_or_create_venv."""
    env_virtualenv = os.environ.get('VIRTUAL_ENV')
    if env_virtualenv:
        return env_virtualenv + '/bin/pip'
    static_paths = [
        path.abspath('env/bin/pip'),
        path.abspath('venv/bin/pip'),
    ]
    for p in static_paths:
        if path.exists(p):
            return p
    out, err = sub.Popen(['pipenv', '--venv'], stdout=sub.PIPE, stderr=sub.PIPE).communicate()
    if out:
        return out.decode('utf8').strip() + '/bin/pip'
    return None


def resolve_pip_or_create_venv() -> str:
    """Find pip, or create it if it doesn't exist."""
    cmd = _resolve_pip_command()
    if cmd:
        return cmd
    try:
        code = sub.Popen(['virtualenv', 'env', '--python', 'python3']).wait()
        if code:
            raise OSError('Failed to create virtualenv.')
    except KeyboardInterrupt:
        shutil.rmtree('env')
        sys.exit(1)
    return path.abspath('env/bin/pip')


def decode_pip_show_output(s: str) -> t.List[t.Dict[str, str]]:
    """Decode the output of pip show, which is a --- separated set
    of email-header encoded key-value pairs.

    Keys can be seen with viv show <package>, but key ones are Name, Requires, and Required-By.
    """
    p = HeaderParser()
    results = []
    for d in s.split('\n---\n'):
        headers = p.parsestr(d)
        results.append(dict(headers.items()))
    return results


def pip_show(*package: str) -> t.List[t.Dict[str, t.Union[str, t.List[str]]]]:
    """Create a mapping of package_name: <dependency data>, where dependency data is the output
    from pip-show.
    """
    pipcmd = _resolve_pip_command()
    args = [pipcmd, 'show']
    args.extend(package)
    out, _ = sub.Popen(args, stdout=sub.PIPE).communicate()
    pip_show_output = decode_pip_show_output(out.decode('utf8'))
    for out in pip_show_output:
        req = out['Requires']
        out['Requires'] = req.split(', ') if req else []
        req = out.get('Required-By')
        out['Required-By'] = req.split(', ') if req else []
    return pip_show_output


REQ_LINE_SPLITTER = re.compile(r'^([A-Za-z0-9-_.]+)([*=>~^]{1,2}[a-zA-z0-9\.]+)?$')


PACKAGE_WHITELIST = {
    'setuptools'
}


def get_installed_packages() -> t.List[t.Dict[str, str]]:
    pipcmd = _resolve_pip_command()
    out, _ = sub.Popen([pipcmd, 'freeze'], stdout=sub.PIPE).communicate()
    result = []
    for install_line in out.decode('utf8').splitlines():
        if install_line.startswith('-e'):
            name = install_line.split('#egg=')[1]
            version = None
        else:
            name, version = tuple(REQ_LINE_SPLITTER.match(install_line).groups())
        result.append(dict(
            Name=name,
            Version=version,
            Install=install_line,
        ))
    return result


def recurse_requirements(o: t.Dict, dependencies, package_list):
    """Populate dictionary o with all dependencies (including sub)
    from the package_list. Can be called recursively.
    """
    for name in package_list:
        name = norm_package_name(name)
        if name in PACKAGE_WHITELIST or name in o:
            continue
        if name not in dependencies:
            raise ValueError('Could not find dependencies for package: ' + name)
        o[name] = dependencies[name]
        if dependencies[name]['Requires']:
            recurse_requirements(o, dependencies, dependencies[name]['Requires'])


def resolve_packages(pipfile_fpath: str):
    """Given a Pipfile, run within a fully installed env
    in order to resolve all dependencies in the Pipfile.

    Return is a tuple of dicts, mapping normalized name to pip-show output.
    """
    requirements = read_pipfile(pipfile_fpath)
    installed = get_installed_packages()
    show_output = pip_show(*tuple(norm_package_name(d['Name']) for d in installed))
    for install, dep in zip(installed, show_output):
        dep['Install'] = install['Install']

    dependencies = {norm_package_name(d['Name']): d for d in show_output}

    full_requirements = {}
    recurse_requirements(full_requirements, dependencies, requirements['packages'].keys())

    dev_requirements = {}
    recurse_requirements(dev_requirements, dependencies, requirements['dev-packages'].keys())

    return full_requirements, dev_requirements
