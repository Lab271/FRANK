#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

def get_version():
    version = {}
    with open(os.path.join(os.path.dirname(__file__), 'src', PACKAGE, '__init__.py')) as f:
        exec(f.read(), version)
    return version['__version__']

setup(
    name='frank',
    version=get_version(),
    description='Vulnerability platform',
    long_description=long_description,
    license='Apache 2.0',
    author='Ilja Heitlager',
    # author_email='',
    maintainer='Ilja Heitlager',
    maintainer_email='iheitlager@schubergphilis.com',
    keywords=["research-tools"],
    url='https://github.com/iheitlager/frank',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    test_suite="tests",
    platforms=["any"],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.11",
        "Intended Audience :: Researchers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English"
    ],
    install_requires=[],
    zip_safe=True,
)