#!/usr/bin/env python3
"""
Setup script for the Python Module Framework.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="python-module-framework",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A modular Python framework for building structured applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/python-module-framework",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries",
    ],
    python_requires=">=3.8",
    install_requires=[
        "aiofiles>=0.8.0",
    ],
    extras_require={
        "system": ["psutil>=5.9.0"],
        "dev": [
            "black>=23.1.0",
            "isort>=5.12.0",
            "pylint>=2.16.0",
            "pytest>=7.2.0",
            "pytest-asyncio>=0.20.0",
            "coverage>=7.1.0",
        ],
    },
)