from setuptools import setup

setup(
    name='timeout-envars',
    version='0.2',
    description='A sample Python package',
    long_description='my test long description',
    author='Keith Harvey',
    author_email='keith.harvey@timeout.com',
    packages=['envars'],
    install_requires=[
        'argparse',
        'pyyaml',
        'boto3',
        'jinja2',
    ],
    entry_points={
        'console_scripts': [
            'envars = envars.envars:main'
        ]
    },
)
