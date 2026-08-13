from setuptools import setup, find_packages

setup(
    name="agentmesh",
    version="2.5.0",
    description="Zuctro AgentMesh Enterprise Control Plane & Governance Gateway CLI",
    author="Zuctro AI",
    py_modules=["cli"],
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "fastapi>=0.110.0",
        "uvicorn>=0.28.0",
        "pydantic>=2.6.0",
        "pyyaml>=6.0.1",
        "grpcio>=1.62.0"
    ],
    entry_points={
        "console_scripts": [
            "agentmesh=cli:main",
        ],
    },
    python_requires=">=3.10",
)
