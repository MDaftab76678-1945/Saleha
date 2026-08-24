from setuptools import setup, find_packages

setup(
    name="saleha",
    version="1.2.0",
    description="Saleha - Self-Healing Multi-Agent AI Framework",
    author="Aftab Alam",
    packages=find_packages(),
    install_requires=[
        "click",
        "rich",
        "requests",
        "psutil",
        "pyyaml",
    ],
    entry_points={
        'console_scripts': [
            'saleha=saleha.cli.commands:cli',
        ],
    },
    python_requires='>=3.9',
)
