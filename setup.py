"""Setup script for pyHidroWeb package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pyhydroweb",
    version="1.0.0",
    author="pyHidroWeb Contributors",
    description="Download Brazilian hydrological data from HidroWeb portal",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/duartejr/pyhidroweb",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: Portuguese (Brazilian)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Hydrology",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pandas>=1.0.0",
        "requests>=2.25.0",
    ],
    extras_require={
        "xarray": ["xarray>=0.16.0"],
        "geopandas": ["geopandas>=0.8.0", "shapely>=1.7.0"],
        "all": [
            "xarray>=0.16.0",
            "geopandas>=0.8.0",
            "shapely>=1.7.0",
        ],
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.12.0",
            "black>=21.0",
            "flake8>=3.9.0",
            "mypy>=0.910",
            "isort>=5.0.0",
        ],
    },
)
