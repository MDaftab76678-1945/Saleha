from setuptools import setup, find_packages

setup(
    name="saleha",
    version="2.6.0",
    description="Local-First Autonomous Multi-Agent AI Software Engineering Platform",
    author="Aftab Alam",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "rich>=13.0.0",
        "pydantic>=2.0.0",
        "requests>=2.31.0",
        "psutil>=5.9.0",
        "pyyaml>=6.0.0",
    ],
    entry_points={
        'console_scripts': [
            'saleha=saleha.cli.commands:cli',
        ],
    },
    python_requires='>=3.10',
)
