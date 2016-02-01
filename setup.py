#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation 
# All rights reserved. 
# 
# Distributed under the terms of the MIT License
#-------------------------------------------------------------------------
import os
import setuptools

from distutils.core import setup, Extension
from Cython.Build import cythonize

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
    version='0.3.2',
    description='Python module for using Project Oxford APIs',
    long_description=long_description,
    author='Microsoft Corporation',
    author_email='python@microsoft.com',
    url='http://github.com/zooba/projectoxford',
    packages=['projectoxford', 'projectoxford.tests'],
    ext_modules=cythonize('projectoxford/_audio_win32.pyx'),
    install_requires=['requests'],
    classifiers=classifiers,
)

setup(**setup_cfg)
