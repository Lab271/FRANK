# FRANK
This is the Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling (FRANK) project. We have developed this in a 4-stage infra scaling process.

<!-- Simple minimalist badge -->
[![Python 3.13](https://img.shields.io/badge/python-v3.13-blue.svg)](https://www.python.org/downloads/release/python-3137/) 
[![Python 3.11](https://img.shields.io/badge/python-v3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

![AWS](https://img.shields.io/badge/AWS-Cloud-orange.svg?style=flat&logo=amazon-aws&logoColor=white)

![latest build](https://github.com/LAB271/FRANK/actions/workflows/main.yml/badge.svg)


This project contains everything from design to implementation of the FRANK project. To get started, clone this project:

```
    $ git clone git@github.com:LAB271/FRANK.git && cd FRANK
```

It assumes Docker/Python/Make/AWS Cli and [uv](https://docs.astral.sh/uv/) as package manager to be available, you can test availability with `make check`

```
    $ make check
    ✅ uv available
    ✅ aws available
    ✅ docker available
    ✅ docker-compose available
    🔧 All required tools available
```

when all tools are available, prep the env:

```
    $ make env                # install all run and dev packages for development
    $ source .*/bin/activate  # start the virtual env  
    $ make test               # run all unittests locally
```

PS I have `alias venv="source .*/bin/activate"` to quickly activate the virtualenv. Your Macbook is now ready to run FRANK locally or through Docker. Some bash scripts are available for testing. Deployment to AWS [stage 3](stages/stage3/README.md) is done through Ansible/AWS CLI and Cloudformation.

You might want to uderstand the [evolutionary design](docs/evolutionary_design.md) principles, before you continue coding on FRANK. 
