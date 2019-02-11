from shlex import quote
import sys
import shutil
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


def _install(pipcmd, packages: t.Tuple[str], dev, save):
    """Installs a specified package, or the entire Pipfile if no package specified."""
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
@click.option('-d', '--dev', help='Save for development.', is_flag=True)
@click.option('--deploy', help='Install from requirements.', is_flag=True)
@click.option('-n', '--no-save', help='Skip saving the requirement.', is_flag=True)
@click.argument('packages', nargs=-1)
def install(packages: t.Tuple[str], dev, deploy, no_save):
    """Installs frozen environment, or adds package to the environment.

    viv install # installs from reqs, including dev
    viv install --deploy # installs from reqs, only deploy
    viv install package # Install package to the environment, saving it
    viv install -d package # Saves package to dev section of Pipfile
    """
    pipcmd = resolve_pip_or_create_venv()
    if not packages:
        args = [pipcmd, 'install', '--no-deps', '-r', 'requirements.txt']
        if not deploy:
            args.extend(['-r', 'requirements-dev.txt'])
        sys.exit(sub.Popen(args).wait())
    else:
        sys.exit(_install(pipcmd, packages, dev, not no_save))


@cli.command()
@click.option('--no-install', help='Skip install step.', is_flag=True)
def lock(no_install):
    """Generate the lockfile.
    """
    pipcmd = resolve_pip_or_create_venv()
    if not no_install:
        _install(pipcmd, tuple(), True, False)

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


def _venv_proc_args(pipcmd: str, subproc_args: t.Opt[t.Tuple[str]]):
    """Generate shell args that run the given command
    in a shell which has the virtualenv activated.

    If no args are given, launch the shell itself.
    """
    pip_cmd = Path(pipcmd)
    shell_cmd = os.environ.get('SHELL', '/bin/bash')
    shell_name = Path(shell_cmd).name
    if shell_name == 'bash':
        activate_cmd = str(pip_cmd.with_name('activate'))
    elif shell_name == 'fish':
        activate_cmd = str(pip_cmd.with_name('activate.fish'))
    elif shell_name == 'csh':
        activate_cmd = str(pip_cmd.with_name('activate.csh'))
    else:
        raise ValueError('Shell doesn\'t appear to be supported by virtualenv: ' + shell_cmd)
    if subproc_args is None:
        subproc_args = [shell_cmd]

    # construct an arg which sets up virtualenv to pass to -c for bash
    arg = ''
    bash_profile = path.abspath(path.expanduser('~/.bash_profile'))
    if path.exists(bash_profile):
        arg += '. ' + quote(bash_profile) + '; '
    arg += '. ' + quote(activate_cmd) + '; '
    arg += ' '.join(quote(s) for s in subproc_args)
    result = [shell_cmd, '-c', arg]
    return result


def _run_in_virtualenv(args: t.Opt[t.Tuple[str]] = None):
    """Run the given args in a virtualenv-activated shell."""
    pipcmd = Path(resolve_pip_or_create_venv())
    args = _venv_proc_args(pipcmd, args)
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
    """Freeze the packages in the env, just like pip freeze."""
    _run_in_virtualenv(('pip', 'freeze'))


@cli.command()
def destroy():
    """Destroy the pip environment."""
    pipcmd = _resolve_pip_command()
    if pipcmd is None:
        return
    out, _ = sub.Popen(_venv_proc_args(pipcmd, ['/bin/bash', '-c', 'echo $VIRTUAL_ENV']),
                       stdout=sub.PIPE).communicate()
    shutil.rmtree(out.decode('utf8').strip())
