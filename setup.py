"""Setup configuration for nb-curator package."""

from setuptools import setup, find_packages

from nb_curator import __version__

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="nb-curator",
    version=__version__,
    author="Todd Miller",
    author_email="jmiller@stsci.edu",
    description="A notebook curation tool for managing Jupyter notebook environments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/spacetelescope/nb-curator",
    packages=find_packages(),
    scripts=["bin/nb-curator"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "ruamel.yaml>=0.17.0",
        "papermill>=2.4.0",
        "ipykernel>=6.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "nb-curator=nb_curator.cli:main",
        ],
    },
)
