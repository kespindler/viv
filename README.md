# Viv

Viv, an easier python packaging tool.

Alpha quality software.

## Why Build It

Pipenv is really, really, really slow.

## How viv works

Viv is a relatively thin wrapper around pip, providing tools for managing a Pipfile and requirements\*.txt files.

You should be able to read the entire codebase in a few hours.

## Workflow

`viv install` to install default and development packages.

`viv install --deploy` to install in production (no dev packages).

`viv install <package>` to install a new package to Pipfile. Use `--dev` to save to dev section.

`viv lock` to create requirements.txt and requirements-dev.txt files.

`viv shell` to open up a shell.

`viv run <bash command>` to run a program. 
    Use `viv run -- <bash command>` if there are conflicting command line arguemnts.

## Outstanding issues

1. Hardcodes all kind of assumptions about bash environment.
2. Hardcodes some assumptions about where to default the virtualenv environment to.
3. It only compares version numbers, but not hashes.
4. No tests.
5. Missing commands: `clean`, `check`, and `new`. Probably other commands too.
