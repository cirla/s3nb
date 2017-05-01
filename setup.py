try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name = 's3nb',
    version = '0.1.0',
    author = "Monetate Inc.",
    author_email = "graphaelli@monetate.com",
    description = "S3 backed notebook manager for jupyter",
    install_requires = ['jupyter', 'boto3'],
    keywords = "ipython jupyter s3",
    license = "MIT",
    long_description = """This package enables storage of .ipynb files in s3""",
    platforms = 'any',
    packages = ['s3nb'],
    url = "https://github.com/monetate/s3nb",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
    ]
)
