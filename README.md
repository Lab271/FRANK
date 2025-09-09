# FRANK
This is the Feedbackinfrastructuur voor cyberRisico Analyse en netwerk Kennisdeling (FRANK) project. We have developed this in a 5-stage infra scaling process.

<!-- Simple minimalist badge -->
[![Python 3.11](https://img.shields.io/badge/python-v3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)

This project contains everything from design to implementation of the FRANK project. To get started, clone this project and run:

```
    $ make dev # crete virtualenv and install all dependencies for development
    $ make env # install all packages for development
    $ source .*/bin/activate. # start the virtual env
    $ make unittests. # run all unittests locally
```

This will prep your Macbook to run FRANK locally. It assumes Docker/Python/Make/AWS Cli to be available.


1. Remove FRANKSubmission/validator, fix all fields
2. Upgrade sqlite client to Submission model
3. Upgrade all spikes/server to Submission model
4. Fix unittests to new model
5. Upgrade BDD to simple models
6. Upgrade stage 1 to models
7. Upgrade stage 2 to models
