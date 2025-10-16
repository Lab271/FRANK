# FRANK
This is the Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling (FRANK) project. We have developed this in a 5-stage infra scaling process.

<!-- Simple minimalist badge -->
[![Python 3.13](https://img.shields.io/badge/python-v3.13-blue.svg)](https://www.python.org/downloads/release/python-3137/) 
[![Python 3.11](https://img.shields.io/badge/python-v3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

![AWS](https://img.shields.io/badge/AWS-Cloud-orange.svg?style=flat&logo=amazon-aws&logoColor=white)

![example workflow](https://github.com/LAB271/FRANK/actions/workflows/main.yml/badge.svg)


This project contains everything from design to implementation of the FRANK project. To get started, clone this project and run:

```
    $ make env                # install all packages for development
    $ source .*/bin/activate  # start the virtual env  
    # PS I have alias venv="source .*/bin/activate"
    $ make test               # run all unittests locally
```

This will prep your Macbook to run FRANK locally. It assumes Docker/Python/Make/AWS Cli to be available, you can test it with `make check`.

Start to understand the [evolutionary design](docs/evolutionary_design.md) principles, before you continue coding on FRANK.
