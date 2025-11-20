"""
Plot Palette - AWS Full-Stack Synthetic Data Generator

Setup script for installing the backend package.
"""

from setuptools import setup, find_packages
import os

# Read requirements from backend/requirements.txt
requirements_path = os.path.join(os.path.dirname(__file__), 'backend', 'requirements.txt')
with open(requirements_path) as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read dev requirements
dev_requirements_path = os.path.join(os.path.dirname(__file__), 'requirements-dev.txt')
with open(dev_requirements_path) as f:
    dev_requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='plot-palette',
    version='1.0.0',
    description='AWS serverless synthetic data generation platform with ECS Fargate Spot workers',
    author='HatmanStack',
    author_email='82614182+HatmanStack@users.noreply.github.com',
    url='https://github.com/HatmanStack/plot-palette',
    packages=find_packages(include=['backend', 'backend.*']),
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements,
    },
    python_requires='>=3.13',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.13',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    include_package_data=True,
    zip_safe=False,
)
