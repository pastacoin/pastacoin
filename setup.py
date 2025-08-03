from setuptools import setup, find_packages

setup(
    name="pastacoin",
    version="0.1.0",
    packages=find_packages(where="."),
    python_requires=">=3.8",
    install_requires=[
        "flask",
        "flask-cors",
        "requests",
        "ecdsa",
        "base58",
        "PySide6>=6.6",
    ],
    description="Experimental Pastacoin blockchain tools",
    author="Leidi",
)
