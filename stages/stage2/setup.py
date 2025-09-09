from setuptools import setup, find_packages

PACKAGE = 'frank'

def get_version():
    version = {}
    with open(os.path.join(os.path.dirname(__file__), PACKAGE, '__init__.py')) as f:
        exec(f.read(), version)
    return version['__version__']

setup(
    name=PACKAGE,
    version=get_version(),
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
            "pytest>=8.4.0",
            "pytest-asyncio>=0.21.0",
            "httpx>=0.25.0",
        ],
    },
)