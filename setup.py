#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# Distributed under the terms of the MIT License
#-------------------------------------------------------------------------
import os
import re
import setuptools

from distutils.core import setup, Extension
from Cython.Build import cythonize

__author__ = 'Microsoft Corporation <python@microsoft.com>'
__version__ = '0.3.2'

AUTHOR_RE = re.match(r'(.+?)\s*\<(.+?)\>', __author__)

with open('README', 'r', encoding='utf-8') as f:
    long_description = f.read()

classifiers = [
    'Development Status :: 3 - Alpha',
    'Environment :: Win32 (MS Windows)',
    'License :: OSI Approved :: MIT License',
    'Natural Language :: English',
    'Operating System :: OS Independent',
    'Operating System :: Microsoft :: Windows',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3 :: Only',
    'Topic :: Multimedia :: Sound/Audio :: Capture/Recording',
    'Topic :: Multimedia :: Sound/Audio :: Players',
    'Topic :: Multimedia :: Sound/Audio :: Speech',
    'Topic :: Text Processing :: Linguistic',
]


setup_cfg = dict(
    name='projectoxford',
    version=__version__,
    description='Python module for using Project Oxford APIs',
    long_description=long_description,
    author=AUTHOR_RE.group(1),
    author_email=AUTHOR_RE.group(2),
    url='http://github.com/zooba/projectoxford',
    packages=['projectoxford', 'projectoxford.tests'],
    ext_modules=cythonize('projectoxford/_audio_win32.pyx') if sys.platform.startswith('win') else None,
    install_requires=['requests'],
    classifiers=classifiers,
)

setup(**setup_cfg)
