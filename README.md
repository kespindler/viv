# Viv

Viv, an easier python packaging tool.

Alpha quality software.

## Workflow

`viv install --dev` to install default and development packages from Pipfile.

`viv install --save <package>` to install a new package to Pipfile.

`viv lock` to create requirements.txt and requirements-dev.txt files.

`viv sync` to install from requirements.txt file.

`viv shell` to open up a shell.

`viv run <bash command>` to run a program. 
    Use `viv run -- <bash command>` if there are conflicting command line arguemnts.


## Outstanding issues

1. Hardcodes all kind of assumptions about bash environment.
2. Hardcodes some assumptions about where to default the virtualenv environment to.
3. No tests.
