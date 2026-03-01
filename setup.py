"""
VelvetEcho Setup Configuration

Install VelvetEcho CLI and libraries:
    pip install -e .

Usage:
    velvetecho --help
    velvetecho generate resource Agent name:str --timestamps
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="velvetecho",
    version="2.0.0",
    description="Enterprise-grade workflow orchestration platform with CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="VelvetEcho Team",
    url="https://github.com/antoinemassih/velvetecho",
    packages=find_packages(exclude=["tests*", "examples*"]),
    python_requires=">=3.10",
    install_requires=[
        # Core dependencies
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.27.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "asyncpg>=0.29.0",
        "pydantic>=2.6.0",
        "redis>=5.0.0",
        # CLI dependencies
        "click>=8.1.0",
        "jinja2>=3.1.0",
        # Database
        "alembic>=1.13.0",
        # Utilities
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "black>=24.0.0",
            "ruff>=0.2.0",
            "mypy>=1.8.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "velvetecho=velvetecho.cli.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: FastAPI",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
