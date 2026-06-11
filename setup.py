from setuptools import setup, find_packages

setup(
    name="loggerbuf",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["telemetry", "debugger", "queue_metrics", "config"],
    install_requires=[
        "protobuf>=5.29.3",
        "click>=8.0.0"
    ],
    entry_points={
        "console_scripts": [
            "loggerbuf=cli.console:cli"
        ]
    }
)
