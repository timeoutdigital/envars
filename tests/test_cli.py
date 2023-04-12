import os
import subprocess
from unittest.mock import MagicMock

import yaml

from envars import envars

CMD = 'python -m envars.envars'


def run_cmd(tmp_path, cmd=None):
    return subprocess.run(f'{CMD} -f {tmp_path}/envars.yml {cmd}', shell=True)


def test_help(tmp_path):
    ret = run_cmd(tmp_path, '')
    assert ret.returncode == 0


def test_init(tmp_path):
    ret = run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    assert ret.returncode == 0
    with open(f'{tmp_path}/envars.yml', 'rb') as envars:
        data = envars.read().decode()
    assert data == """configuration:

  APP: testapp

  ENVIRONMENTS:
  - prod
  - staging

  KMS_KEY_ARN: abc

environment_variables: {}
"""


def test_add_default(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'add TEST=test')
    assert ret.returncode == 0
    with open(f'{tmp_path}/envars.yml', 'rb') as envars:
        yml = yaml.load(envars, Loader=yaml.SafeLoader)
    assert yml['environment_variables']['TEST']['default'] == 'test'


def test_add_prod(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'add -e prod TEST=test')
    assert ret.returncode == 0
    with open(f'{tmp_path}/envars.yml', 'rb') as envars:
        yml = yaml.load(envars, Loader=yaml.SafeLoader)
    assert yml['environment_variables']['TEST']['prod'] == 'test'


def test_add_prod_master(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'add -e prod -a master TEST=test')
    assert ret.returncode == 0
    with open(f'{tmp_path}/envars.yml', 'rb') as envars:
        yml = yaml.load(envars, Loader=yaml.SafeLoader)
    assert yml['environment_variables']['TEST']['prod']['master'] == 'test'


def test_add_invalid_stage_fails(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'add -e foo TEST=test')
    assert ret.returncode == 1


def test_add_invalid_account_fails(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'add -a foo TEST=test')
    assert ret.returncode == 1


def test_prod_account_value_returned(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    run_cmd(tmp_path, 'add TEST=dtf')
    run_cmd(tmp_path, 'add -a master -e prod TEST=prod-master')
    run_cmd(tmp_path, 'add -a sandbox -e prod TEST=prod-sandbox')
    ret = subprocess.run(f'{CMD} -f {tmp_path}/envars.yml print -e prod -a master', shell=True, capture_output=True)
    assert ret.stdout.decode() == 'TEST=prod-master\n'


def test_eqauls_in_value(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'TEST1=abc=',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
    )

    assert ret == ['TEST1=abc=']


def test_two_env_vars_returned(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'TEST1=A',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)
    args = type('Args', (object,), {
        'variable': 'TEST2=B',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
    )

    assert ret == ['TEST1=A', 'TEST2=B']


def test_template_var(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'DOMAIN=timeout.com',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)
    args = type('Args', (object,), {
        'variable': 'HOSTNAME=test.{{ DOMAIN }}',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
    )

    assert ret == ['DOMAIN=timeout.com', 'HOSTNAME=test.timeout.com']


def test_extra_template_passing(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'RELEASE={{ RELEASE }}',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
        template_var=['RELEASE=12324523523523525234523523'],
    )

    assert ret == ['RELEASE=12324523523523525234523523']


def test_yaml_print_env(tmp_path):
    # used by deploy playbooks
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'RELEASE={{ RELEASE }}',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)
    args = type('Args', (object,), {
        'variable': 'TEST=test',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)
    args = type('Args', (object,), {
        'variable': 'STEST=stest',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'staging',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
        as_yaml=True,
        template_var=['RELEASE=12324523523523525234523523'],
    )

    assert ret == "envars:\n  RELEASE: '12324523523523525234523523'\n  TEST: test\n"


def test_secret(kms_stub, tmp_path):
    kms_stub.add_response(
        'encrypt',
        service_response={'CiphertextBlob': b'dfghsdghfsd'}
    )
    kms_stub.add_response(
        'decrypt',
        service_response={'KeyId': 'TEST', 'Plaintext': b'sssssh', 'EncryptionAlgorithm': 'SYMMETRIC_DEFAULT'}
    )
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Arg', (object,), {
        'variable': 'TEST=sssssh',
        'secret': True,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
    )

    assert ret == ['TEST=sssssh']


def test_parameter_store_value(ssm_stub, tmp_path):
    ssm_stub.add_response(
        'get_parameter',
        service_response={'Parameter': {'Value': '1234'}}
    )
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Arg', (object,), {
        'variable': 'PTEST=parameter_store:/gp-web/prod/1234/CANARY',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
        template_var=['RELEASE=1234'],
    )

    assert ret == ['PTEST=1234']


def test_exec_one_var(tmp_path):
    # used by some instance service scripts
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'TEST=test',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)
    args = type('Args', (object,), {
        'variable': 'STEST=stest',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    args = type('Args', (object,), {
        'account': None,
        'command': ['printenv'],
        'env': 'prod',
        'filename': f'{tmp_path}/envars.yml',
        'var': 'TEST',
        'quote': False,
        'no_templating': False,
    })
    envars.os.execlp = MagicMock()
    envars.execute(args)

    assert os.environ.get('TEST') == 'test'
    assert 'STEST' not in os.environ


def test_exec(tmp_path):
    # used by some instance service scripts
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'TEST=test',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)
    args = type('Args', (object,), {
        'variable': 'STEST=stest=',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    args = type('Args', (object,), {
        'account': None,
        'command': ['printenv'],
        'env': 'prod',
        'filename': f'{tmp_path}/envars.yml',
        'var': None,
        'template_var': [],
        'quote': False,
        'no_templating': False,
    })
    envars.os.execlp = MagicMock()
    envars.execute(args)

    assert os.environ.get('TEST') == 'test'
    assert os.environ.get('STEST') == 'stest='


def test_secrets_only(kms_stub, tmp_path):
    kms_stub.add_response(
        'encrypt',
        service_response={'CiphertextBlob': b'dfghsdghfsd'}
    )
    kms_stub.add_response(
        'decrypt',
        service_response={'KeyId': 'STEST', 'Plaintext': b'stest', 'EncryptionAlgorithm': 'SYMMETRIC_DEFAULT'}
    )
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'TEST=test',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)
    args = type('Args', (object,), {
        'variable': 'STEST=stest',
        'secret': True,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
        secrets_only=True,
    )

    assert ret == ['STEST=stest']


def test_secrets_only_yaml(kms_stub, tmp_path):
    kms_stub.add_response(
        'encrypt',
        service_response={'CiphertextBlob': b'dfghsdghfsd'}
    )
    kms_stub.add_response(
        'decrypt',
        service_response={'KeyId': 'STEST', 'Plaintext': b'stest', 'EncryptionAlgorithm': 'SYMMETRIC_DEFAULT'}
    )
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'TEST=test',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)
    args = type('Args', (object,), {
        'variable': 'STEST=stest',
        'secret': True,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    ret = envars.process(
        filename=f'{tmp_path}/envars.yml',
        account=None,
        env='prod',
        decrypt=True,
        secrets_only=True,
        as_yaml=True,
    )

    assert ret == 'envars:\n  STEST: stest\n'
