import subprocess

import yaml


def run_cmd(tmp_path, cmd=None):
    return subprocess.run(f'python -m envars.envars -f {tmp_path}/envars.yml {cmd}', shell=True)


def test_help(tmp_path):
    ret = run_cmd(tmp_path, '')
    assert ret.returncode == 0


def test_init(tmp_path):
    ret = run_cmd(tmp_path, 'init --app testapp --envs prod,staging')
    assert ret.returncode == 0
    with open(f'{tmp_path}/envars.yml', 'rb') as envars:
        data = envars.read().decode()
    assert data == 'configuration:\n  APP: testapp\n  ENVIRONMENTS:\n  - prod\n  - staging\nenvironment_variables: {}\n'


def test_add_default(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --envs prod,staging')
    ret = run_cmd(tmp_path, 'add -v TEST=test')
    assert ret.returncode == 0
    with open(f'{tmp_path}/envars.yml', 'rb') as envars:
        yml = yaml.load(envars, Loader=yaml.SafeLoader)
    assert yml['environment_variables']['TEST']['default'] == 'test'


def test_add_prod(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --envs prod,staging')
    ret = run_cmd(tmp_path, 'add -e prod -v TEST=test')
    assert ret.returncode == 0
    with open(f'{tmp_path}/envars.yml', 'rb') as envars:
        yml = yaml.load(envars, Loader=yaml.SafeLoader)
    assert yml['environment_variables']['TEST']['prod'] == 'test'


def test_add_prod_master(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --envs prod,staging')
    ret = run_cmd(tmp_path, 'add -e prod -a master -v TEST=test')
    assert ret.returncode == 0
    with open(f'{tmp_path}/envars.yml', 'rb') as envars:
        yml = yaml.load(envars, Loader=yaml.SafeLoader)
    assert yml['environment_variables']['TEST']['prod']['master'] == 'test'


def test_add_invalid_stage_fails(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --envs prod,staging')
    ret = run_cmd(tmp_path, 'add -e foo -v TEST=test')
    assert ret.returncode == 1


def test_add_invalid_account_fails(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --envs prod,staging')
    ret = run_cmd(tmp_path, 'add -a foo -v TEST=test')
    assert ret.returncode == 1
