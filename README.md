# nb-curator

## Overview

This is a prototype of a notebook curation tool which enables a curator to
specify a set of notebooks and requirements which will then be used as the
basis for defining a Python environment suitable for running all of them.  In
addition to defining a precise set of package versions to install, it collects
inputs for testing the resulting environment and runners which execute the
tests.  The long term goal of this tool is to provide inputs to build and test
Jupyter notebook Docker images in a CI/CD pipeline enabling curators to deploy
science platform notebook images with minimal interaction with platform
administrators.

## Precusor

It has to be said that we're on somewhat shaky ground by initially
side-stepping Docker for the sake of easing the curation process.  On
the other hand, I don't think we're really tackling massive
portability issues the astronomical community at large is not already
familiar with.  To the extent that native micromamba and mamba
installs of our requirements work, and the resolved dependencies are
portable... this has a good chance of providing a solid workflow to
feed our Docker builds.  Indeed, this workflow will include any
generic requirements being imposed by the science platform for a
curator to see and resolve or start working in real time...  before
even tangling with real Docker builds.  The final caveat though is
that the Docker image is a different environment so unforseen gotchas
may arise and this process may need a corresponding overhaul.

There are a couple of relatively new foundational tools being used here:

- micromamba -- a self-contained little brother of mamba (the better free OSS version of conda)
- uv -- a whole new installation system written in Rust which can be pip installed == fast dependency solutions? fast installs?

The intent of `nb-curator` is to install 2-3 dedicated environments under `$HOME/.nb-curator`:

- micromamba -- self-contained minimalistic install tool, not a base environment 
- nbcurator  -- a true micromamba environment in which nb-curator runs with required dependencies
- <target environment> -- the mamba environment we're curating defined by the YAML spec (or, possibly, CLI)

## Installing

Bootstrapping the system will create the .nb-curator dir and nbcurator environment under $HOME.

```
git clone git+https://github.com/spacetelescope/nb-curator
cd nb-curator
bin/nb-curator bootstrap
```

After that, the environment can be activated using:

XXXXX

## Example Usage

Curator prepares custom version of prototype_protocol.yaml
Curator prepares a curation Python environment with the spec'ed version of Python
Then:
```
./nb_curator.py  spec.yaml  --create-env

./nb_curator.py  spec.yaml  --init-env

./nb_curator.py  spec.yaml  --clone  [ --repos-dir notebook-repos ]

./nb_curator.py  spec.yaml   --compile

./nb_curator.py  spec.yaml   --install

./nb_curator.py  spec.yaml   --test

./nb_curator.py  spec.yaml   --cleanup

./nb_curator.py  spec.yaml   --wipe-env

./nb_curator.py  spec.yaml   --submit-for-build

./nb_curator.py  spec.yaml   --generate-deployment
```

## Basic Flow

The basic flow of the curator is to command different steps of the overall
process to execute or not on a per-run basis.  Eventually this enables skipping
over aspects of the process which have already been successfully completed and
iterating on the current task, e.g. not constantly recompiling and
re-installing pacackages while iterating over failing notebook tests and
notebook updates.  If any step in the sequence fails, the process will exit
with an error status.  The following features/steps are generally gated by CLI
switches.

- Loads, validates, updates, and saves the YAML notebook specification.
  Validation is currently incomplete but checks for required keywords.

- Optionally clones the git repositories for the notebooks if a
  local clone does not already exist,  otherwise it updates the existing clones
  from their repos or does nothing if --clone is not specified.  --repos-dir is
  used to specify the directory where the git repositories are cloned and/or
  already exist, defaulting to a notebook-repos subdir of the current directory.

- Searches for relevant notebooks based on the notebook directory paths and
  include/exclude patterns.

- Searches for requirements.txt files which specify Python package version
  constraints at a granular level of single notebooks.  Exactly what to include
  is a WIP,  but at a minimum one optional requirements.txt per notebook.

- Optionally creates a basic Python environment in which packages will be
  installed and tested.   The overall paradigm of the nb-curator tool is
  that it installs packages and tests notebooks with respect to the current
  Python environment.  The --create-env [envname] switch creates virtual
  environment dedicated to the development of this particular curation spec.
  In addition to supporting development and test,  it supports complete cleanup
  and guarantees a pristine environment relative to which notebook requirements
  should be resolved and installed.  (not implemented yet)

- Optionally initializes (--init-env) a target environment to support
  compilation of requirements, package installation, and testing.  In addition
  to installing a handful of utility packages, it creates a JupyterLab kernel
  for the environment that is required for notebook testing or using it in
  JupyterLab.  This is useful even if the curator chooses to use their own
  custom environment as the target since these packages and kernel setup
  are required regardless.

- If --compile is specified, it will create both a conda environment .yml file
  and a locked pip requirements.txt file based on compiling all the discovered
  notebook requirements.txt simultaneously, with the goal of creating a package
  version spec suitable for running ALL of the notebooks.  If --compile is not
  specified it will continue to use the last set of compiled packages from the
  spec.

- If --install is specified, it will install the compiled versions of packages
  in the conda environment, which XXXXX again at this time is the runtime
  environment. After installation, it will attempt to import any package which
  is explicitlylisted in a notebook file as a basic sanity check.

- If --test-notebooks is specified, run notebooks matching any of the
subsequent comma separated list of notebook names or regular expressions.  If
no notebooks or regexps are specified, it will run all notebooks.  This is a
headless crash test which runs up to --jobs [n] notebooks in parallel using a
--timeout [seconds] to kill runaway notebooks.

- If --cleanup is specified,  it will remove all cloned repositories.

- If a proposed/not-implemented --wipe-env is specified,  it will remove the
  target environment.   This dedicated environment approach prevents contamination
  between iterations of the tool as packages come-and-go from the spec but are
  never removed from the target environment.

- If optional/proposed --submit-for-build is specified,  the spec is forwarded
  to the CI chain,  key information is supplied to the build framework, and a
  corresponding image is automatically built and pushed to the hub assuming all
  goes well.   This is all still TBD pending interest/approval of the above.
