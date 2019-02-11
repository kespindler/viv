from setuptools import setup, find_packages

setup(
    name='viv',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'Click',
        'plette',
    ],
    entry_points={
        'console_scripts': [
            'viv = viv.cli:cli',
        ],
    }
)
