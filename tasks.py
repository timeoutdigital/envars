import logging
import os
import subprocess
import sys

from invoke import task

logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s - %(message)s')

APP_NAME = 'envars'
PYTHON_VERSION = 3.10


def confirm(message):
    print(message)
    choice = input().strip().lower()
    return choice == 'y'


def get_branch_name():
    branch_name = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip().decode()
    print(f"Current branch name: {branch_name}")
    return branch_name


def get_python_version(file_path='PYTHON_VERSION'):
    if not os.path.exists(file_path):
        logging.info(f'Error: File {file_path} does not exist')
        return PYTHON_VERSION

    try:
        with open(file_path, 'r') as f:
            version = f.read().strip()
            if not version:
                logging.info('Error: File is empty')
                return None

            return version
    except Exception as e:
        logging.info(f'An error occurred while reading file: {e}')
        return None


@task
def python_deps_upgrade(c):
    """Update pip requirements"""
    c.run('pip-compile --resolver=backtracking -U')
    c.run('pip install -r requirements.txt')


@task
def python(c):
    """Configure python virtualenv"""
    python_version = get_python_version()
    branch = get_branch_name()
    env_name = f'{APP_NAME}_{branch}'
    c.run(f'pyenv install -s {python_version}')
    with open('.python-version', 'w') as f:
        f.write(env_name)
    c.run(f'pyenv virtualenv {python_version} {env_name}')
    with c.prefix(f'eval "$(pyenv init -)" && pyenv activate {env_name}'):
        c.run('pip install -r requirements.txt')
        c.run('pip install wheel')
        c.run('pre-commit install')
        print(f'Activate env: `pyenv activate {env_name}`')


@task
def test(c):
    """Execute pytest"""
    c.run('pytest -v', pty=True)


@task
def clean(c):
    """Cleanup python environment"""
    if os.path.exists('.python-version'):
        with open('.python-version') as f:
            virtual_env = f.read().strip()
            if not confirm("Are you sure?"):
                logging.info("You failed to confirm the command")
                sys.exit(1)
            os.remove('.python-version')
            c.run(f'eval "$(pyenv init -)" && pyenv virtualenv-delete -f {virtual_env}')
