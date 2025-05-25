from setuptools import setup, find_packages

setup(
    name="nlweb",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        # Add your project's dependencies here
    ],
    python_requires=">=3.8",
)
