from shlex import quote
import sys
import os
from os import path
import viv.types as t
from pathlib import Path
from viv.resolver import (
    resolve_packages, read_pipfile, REQ_LINE_SPLITTER, resolve_pip_or_create_venv,
    _resolve_pip_command,
)
from viv.parser import pip_args_from_pipfile_line, write_requirements_file
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
    key = '__PYVENV_LAUNCHER__'
    if key in os.environ:
        del os.environ[key]


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    fix_environ()


def _install(packages: t.Tuple[str], dev, save):
    """Installs a specified package, or the entire Pipfile if no package specified."""
    pipcmd = resolve_pip_or_create_venv()
    args = [pipcmd, 'install']
    if packages:
        args.extend(packages)
    else:
        pipfile = read_pipfile('Pipfile')
        for pair in pipfile.packages.items():
            args.extend(pip_args_from_pipfile_line(pair))
        if dev:
            for pair in pipfile.dev_packages.items():
                args.extend(pip_args_from_pipfile_line(pair))
    rc = sub.Popen(args).wait()
    if rc:
        return rc
    if save:
        if not packages:
            print('No packages were supplied to save.')
            return 1
        pipfile = read_pipfile('Pipfile')
        package_list = pipfile.packages if dev else pipfile.dev_packages

        for p in packages:
            name, ver = REQ_LINE_SPLITTER.match(p).groups()
            package_list[name] = ver or '*'

        pipfile.dump(open('Pipfile', 'w'))
    return 0


@cli.command()
@click.option('-d', '--dev', help='Install for development.', is_flag=True)
@click.option('--default', help='Install for default.', is_flag=True)
@click.option('-s', '--save', help='Save to Pipfile.', is_flag=True)
@click.argument('packages', nargs=-1)
def install(packages: t.Tuple[str], dev, default, save):
    """Installs a specified package, or the entire Pipfile if no package specified.

    viv install # installs from Pipfile, including dev
    viv install --default # installs only the defaults
    viv install -s package # Saves package to default section of Pipfile
    viv install -sd package # Saves package to dev section of Pipfile
    """
    if packages and default:
        raise ValueError('If you include packages, prod is the default.')
    if not packages:
        dev = not default
    sys.exit(_install(packages, dev, save))


@cli.command()
@click.option('--no-install', help='Skip install step.', is_flag=True)
def lock(no_install):
    """Generate the lockfile.
    """
    if not no_install:
        _install(tuple(), True, False)

    default, dev = resolve_packages('Pipfile')

    write_requirements_file(default, 'requirements.txt')
    write_requirements_file(dev, 'requirements-dev.txt')


@cli.command()
@click.option('--dev', help='Install for development.', is_flag=True)
def sync(dev=False):
    """Install from the lock file.
    """
    pipcmd = resolve_pip_or_create_venv()
    args = [pipcmd, 'install', '--no-deps', '-r', 'requirements.txt']
    if dev:
        args.extend(['-r', 'requirements-dev.txt'])
    sys.exit(sub.Popen(args).wait())


def _venv_proc_args(subproc_args: t.Opt[t.Tuple[str]]):
    """Generate shell args that run the given command
    in a shell which has the virtualenv activated.

    If no args are given, launch the shell itself.
    """
    pipcmd = Path(resolve_pip_or_create_venv())
    shell_cmd = os.environ.get('SHELL', '/bin/bash')
    shell_name = Path(shell_cmd).name
    if shell_name == 'bash':
        activate_cmd = str(pipcmd.with_name('activate'))
    elif shell_name == 'fish':
        activate_cmd = str(pipcmd.with_name('activate.fish'))
    elif shell_name == 'csh':
        activate_cmd = str(pipcmd.with_name('activate.csh'))
    else:
        raise ValueError('Shell doesn\'t appear to be supported by virtualenv: ' + shell_cmd)
    if subproc_args is None:
        subproc_args = [shell_cmd]

    # construct an arg which sets up virtualenv to pass to -c for bash
    arg = ''
    bash_profile = path.abspath(path.expanduser('~/.bash_profile'))
    if path.exists(bash_profile):
        arg += '. ' + quote(bash_profile) + ';'
    arg += '. ' + quote(activate_cmd) + ';'
    arg += ' '.join(quote(s) for s in subproc_args)
    return [shell_cmd, '-c', arg]


def _run_in_virtualenv(args: t.Opt[t.Tuple[str]] = None):
    """Run the given args in a virtualenv-activated shell."""
    args = _venv_proc_args(args)
    os.execv(args[0], args)


@cli.command()
def shell():
    """Open a shell with the virtualenv activated.
    """
    _run_in_virtualenv()


@cli.command()
@click.argument('args', nargs=-1)
def run(args: t.Tuple[str]):
    """Open a shell with the virtualenv activated.
    """
    _run_in_virtualenv(args)


@cli.command()
@click.argument('packages', nargs=-1)
def show(packages: t.Tuple[str]):
    """Open a shell with the virtualenv activated.
    """
    _run_in_virtualenv(tuple(['pip', 'show'] + list(packages)))


@cli.command()
def env():
    """Display the virtualenv path."""
    pip_command = _resolve_pip_command()
    if pip_command is None:
        print('No virtualenv found.')
        sys.exit(1)
    print(Path(pip_command).parent.parent)


@cli.command()
def freeze():
    """Freeze the pip environment."""
    _run_in_virtualenv(('pip', 'freeze'))
