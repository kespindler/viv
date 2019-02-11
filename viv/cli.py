from shlex import quote
import os
from typing import Tuple, Optional as Opt, Union, Dict
from plette.models import Package
from pathlib import Path
from viv.resolver import resolve_packages, read_pipfile, REQ_LINE_SPLITTER, \
    resolve_pip_or_create_venv
import click
import subprocess as sub

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


def fix_environ():
    """Hack to get around this issue: https://github.com/python/cpython/pull/9516

    Without it, try running `viv install ipython` and you'll find that head -n1 env/bin/ipython
    leads to /usr/local/bin/python instead of env/bin/python.

    Ultimately also led to a nasty path issue where flask server restarter would fail to use the
    venv.
    """
    if '__PYVENV_LAUNCHER__' in os.environ:
        del os.environ['__PYVENV_LAUNCHER__']


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    fix_environ()


def pip_line_from_pipfile_line(pair: Tuple[str, Package]):
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


def _install(packages: Tuple[str], dev, save):
    """Installs a specified package, or the entire Pipfile if no package specified."""
    pipcmd = resolve_pip_or_create_venv()
    args = [pipcmd, 'install']
    if packages:
        args.extend(packages)
    else:
        pipfile = read_pipfile('Pipfile')
        for pair in pipfile.packages.items():
            args.extend(pip_line_from_pipfile_line(pair))
        if dev:
            for pair in pipfile.dev_packages.items():
                args.extend(pip_line_from_pipfile_line(pair))
    sub.Popen(args).wait()
    if save:
        if not packages:
            print('No packages were supplied to save.')
            return
        pipfile = read_pipfile('Pipfile')
        package_list = pipfile.packages if dev else pipfile.dev_packages

        for p in packages:
            name, ver = REQ_LINE_SPLITTER.match(p).groups()
            package_list[name] = ver or '*'

        pipfile.dump(open('Pipfile', 'w'))


@cli.command()
@click.option('--dev', help='Install for development.', is_flag=True)
@click.option('--save', help='Save to Pipfile.', is_flag=True)
@click.argument('packages', nargs=-1)
def install(packages: Tuple[str], dev, save):
    """Installs a specified package, or the entire Pipfile if no package specified."""
    _install(packages, dev, save)


@cli.command()
@click.option('--no-install', default=False, help='Skip install step.', is_flag=True)
def lock(no_install):
    """Generate the lockfile.
    """
    if not no_install:
        _install(tuple(), True, False)

    default, dev = resolve_packages('Pipfile')

    with open('requirements.txt', 'w') as f:
        requirements = sorted(
            '{name}=={version}'.format(name=d['Name'], version=d['Version'])
            for d in default.values()
        )
        f.write('\n'.join(requirements))

    with open('requirements-dev.txt', 'w') as f:
        requirements = sorted(
            '{name}=={version}'.format(name=d['Name'], version=d['Version'])
            for d in dev.values()
        )
        f.write('\n'.join(requirements))


def run_install(pipcmd, fpath):
    sub.Popen([pipcmd, 'install', '--no-deps', '-r', fpath]).wait()


@cli.command()
@click.option('--dev', help='Install for development.', is_flag=True)
def sync(dev=False):
    """Install from the lock file.
    """
    pipcmd = resolve_pip_or_create_venv()
    fpath = 'requirements.txt'
    run_install(pipcmd, fpath)
    if dev:
        fpath = 'requirements-dev.txt'
        run_install(pipcmd, fpath)


def venv_subproc(args: Opt[Tuple[str]]):
    pipcmd = resolve_pip_or_create_venv()
    activate_cmd = str(Path(pipcmd).with_name('activate'))
    shell_cmd = '/bin/bash'
    arg = '. ' + '~/.bash_profile' + ';. ' + quote(activate_cmd) + '; '
    shell_args = [shell_cmd, '-c']
    if args is None:
        args = [shell_cmd]
    arg += ' '.join(quote(s) for s in args)
    shell_args.append(arg)
    return shell_args


def _run_in_virtualenv(args: Opt[Tuple[str]] = None):
    args = venv_subproc(args)
    os.execv(args[0], args)


@cli.command()
def shell():
    """Open a shell with the virtualenv activated.
    """
    _run_in_virtualenv()


@cli.command()
@click.argument('args', nargs=-1)
def run(args: Tuple[str]):
    """Open a shell with the virtualenv activated.
    """
    # print('\n'.join(k + '=' + 'v' for k, v in sorted(os.environ.items())))
    _run_in_virtualenv(args)


@cli.command()
@click.argument('packages', nargs=-1)
def show(packages: Tuple[str]):
    """Open a shell with the virtualenv activated.
    """
    # print('\n'.join(k + '=' + 'v' for k, v in sorted(os.environ.items())))
    _run_in_virtualenv(tuple(['pip', 'show'] + list(packages)))
