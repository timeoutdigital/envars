import subprocess

import yaml

CMD = 'python -m envars.envars'


def run_cmd(tmp_path, cmd=None):
    return subprocess.run(f'{CMD} -f {tmp_path}/envars.yml {cmd}', shell=True)


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


def test_prod_account_value_returned(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --envs prod,staging')
    run_cmd(tmp_path, 'add -v TEST=dtf')
    run_cmd(tmp_path, 'add -a master -e prod -v TEST=prod-master')
    run_cmd(tmp_path, 'add -a sandbox -e prod -v TEST=prod-sandbox')
    ret = subprocess.run(f'{CMD} -f {tmp_path}/envars.yml print -e prod -a master', shell=True, capture_output=True)
    assert ret.stdout.decode() == 'TEST=prod-master\n'


def test_secret(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --envs prod,staging')
    run_cmd(tmp_path, 'add -s -v TEST=sssssh')
    ret = subprocess.run(f'{CMD} -f {tmp_path}/envars.yml print -d -e prod', shell=True, capture_output=True)
    assert ret.stdout.decode() == 'TEST=sssssh\n'
