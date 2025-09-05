from setuptools import setup, find_packages

setup(
    name="frank",
    version="0.0.0-dev",
    description="FRANK Platform - Feedback Infrastructure for Cyber Risk Analysis",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0", 
        "pydantic>=2.5.0",
        "pymysql>=1.1.0",
        "requests>=2.31.0",
        "python-multipart>=0.0.6",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "httpx>=0.25.0",
        ],
    },
)