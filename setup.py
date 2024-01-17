from setuptools import setup

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='envars',
    version='1.1',
    description='Time Out Envars',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/timeoutdigital/envars',
    author='Keith Harvey',
    author_email='keith.harvey@timeout.com',
    packages=['envars'],
    install_requires=[
        'argparse',
        'pyyaml',
        'boto3',
        'jinja2',
    ],
    extra_require={
        'dev': ["pytest"],
    },
    entry_points={
        'console_scripts': [
            'envars = envars.envars:main'
        ]
    },
    python_requires='>=3.8',
)
