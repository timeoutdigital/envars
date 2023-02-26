from setuptools import setup

setup(
    name='envars',
    version='0.1',
    description='A sample Python package',
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
