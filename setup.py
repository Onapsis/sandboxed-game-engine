import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name="turnboxed",
    version="0.0.4",
    author="Pedro Guridi",
    author_email="pedro.guridi@gmail.com",
    description=("A turn based Python game engine for coding challenge  "
                 "games with sandboxing for each player. Uses the PyPy sandbox."),
    license="MIT",
    keywords="game engine coding challenge",
    url="http://packages.python.org/sandboxed-game-engine",
    packages=['turnboxed'],
    provides=['turnboxed'],
    install_requires=[
        "requests",
    ],
    long_description=read('README'),
    classifiers=[
        'Intended Audience :: Developers',
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "License :: OSI Approved :: BSD License",
    ],
)
