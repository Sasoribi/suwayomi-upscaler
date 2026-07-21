from setuptools import setup, find_packages

setup(
    name="suwayomi-upscaler",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "flask>=3.0,<4.0",
        "gunicorn>=22.0,<23.0",
        "gevent>=24.0,<25.0",
        "Pillow>=10.0,<12.0",
        "requests>=2.31,<3.0",
    ],
    python_requires=">=3.11",
)
