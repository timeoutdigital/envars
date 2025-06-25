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


def test_print_invalid_stage_fails(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'print -e foo')
    assert ret.returncode == 1


def test_print_invalid_stage_override(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'print -e foo -n')
    assert ret.returncode == 0


def test_exec_invalid_stage_fails(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'exec -e foo printenv')
    assert ret.returncode == 1


def test_exec_invalid_stage_overide(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn a-kms-key-arn')
    ret = run_cmd(tmp_path, 'exec -e foo -n printenv')
    assert ret.returncode == 0


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

    args = type('Args', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'account': None,
        'template_var': [],
        'yaml': False,
        'decrypt': True,
        'quote': False,
        'no_check_env': False,
    })
    ret = envars.process(args)

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

    args = type('Args', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'account': None,
        'template_var': [],
        'yaml': False,
        'decrypt': True,
        'quote': False,
        'no_check_env': False,
    })
    ret = envars.process(args)

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

    args = type('Args', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'account': None,
        'template_var': [],
        'yaml': False,
        'decrypt': True,
        'quote': False,
        'no_check_env': False,
    })
    ret = envars.process(args)

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

    args = type('Args', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'account': None,
        'yaml': False,
        'decrypt': True,
        'template_var': ['RELEASE=12324523523523525234523523'],
        'quote': False,
        'no_check_env': False,
    })
    ret = envars.process(args)

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

    args = type('Args', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'var': None,
        'account': None,
        'yaml': True,
        'decrypt': True,
        'template_var': ['RELEASE=12324523523523525234523523'],
        'quote': False,
        'no_check_env': False,
    })
    ret = envars.process(args)

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
    args = type('Arg', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'account': None,
        'template_var': [],
        'yaml': False,
        'decrypt': True,
        'quote': False,
        'no_check_env': False,
    })
    ret = envars.process(args)

    assert ret == ['TEST=sssssh']


def test_parameter_store_value(ssm_stub, tmp_path):
    ssm_stub.add_response(
        'get_parameter',
        service_response={'Parameter': {'Value': '1234'}},
        expected_params={'Name': '/gp-web/prod/1234/CANARY', 'WithDecryption': True},
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

    args = type('Arg', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'account': None,
        'template_var': ['RELEASE=1234'],
        'yaml': False,
        'decrypt': False,
        'quote': False,
        'no_check_env': False,
    })
    ret = envars.process(args)
    assert ret == ['PTEST=1234']


def test_stage_template_parameter_store_value(ssm_stub, tmp_path):
    ssm_stub.add_response(
        'get_parameter',
        service_response={'Parameter': {'Value': '1234'}},
        expected_params={'Name': '/gp-web/prod/1234/CANARY', 'WithDecryption': True},
    )
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Arg', (object,), {
        'variable': 'PTEST=parameter_store:/gp-web/{{ STAGE }}/1234/CANARY',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    args = type('Arg', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'account': None,
        'template_var': ['RELEASE=1234'],
        'yaml': False,
        'decrypt': False,
        'quote': False,
        'no_check_env': False,
    })
    ret = envars.process(args)
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
        'quote': False
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
        'no_check_env': False,
    })
    envars.os.execlp = MagicMock()
    envars.execute(args)

    assert os.environ.get('TEST') == 'test'
    assert os.environ.get('STEST') == 'stest='


def test_var_from_env(tmp_path):
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    args = type('Args', (object,), {
        'variable': 'TEST={{ RELEASE }}',
        'secret': False,
        'filename': f'{tmp_path}/envars.yml',
        'env': 'default',
        'desc': None,
        'account': None,
    })
    envars.add_var(args)

    args = type('Arg', (object,), {
        'filename': f'{tmp_path}/envars.yml',
        'env': 'prod',
        'account': None,
        'template_var': [],
        'yaml': False,
        'decrypt': False,
        'quote': False,
        'no_check_env': False,
    })
    os.environ["RELEASE_SHA"] = '12345'
    ret = envars.process(args)
    assert ret == ['TEST=12345']


def test_validate_success(tmp_path):
    """test valid configuration is successful"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')
    run_cmd(tmp_path, 'add TEST_VAR=test')
    run_cmd(tmp_path, 'add -e prod PROD_VAR=prod-value')
    run_cmd(tmp_path, 'add -e staging -a master STAGING_VAR=staging-master')

    ret = run_cmd(tmp_path, 'validate')
    assert ret.returncode == 0


def test_validate_lowercase_var_fails(tmp_path):
    """test lowercase variable names"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  KMS_KEY_ARN: abc

environment_variables:
  test_var:
    default: value
""")

    ret = subprocess.run(
        f'{CMD} -f {tmp_path}/envars.yml validate',
        shell=True,
        capture_output=True,
        text=True
    )
    assert ret.returncode == 1
    assert 'var name "test_var" is not uppercase' in ret.stdout


def test_validate_mixed_case_var_fails(tmp_path):
    """test mixed case variable names"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  KMS_KEY_ARN: abc

environment_variables:
  TestVar:
    default: value
""")

    ret = subprocess.run(
        f'{CMD} -f {tmp_path}/envars.yml validate',
        shell=True,
        capture_output=True,
        text=True
    )
    assert ret.returncode == 1
    assert 'var name "TestVar" is not uppercase' in ret.stdout


def test_validate_unknown_env_fails(tmp_path):
    """test unkown environment fails validation"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  KMS_KEY_ARN: abc

environment_variables:
  TEST_VAR:
    default: value
    development: dev-value
""")

    ret = subprocess.run(
        f'{CMD} -f {tmp_path}/envars.yml validate',
        shell=True,
        capture_output=True,
        text=True
    )
    assert ret.returncode == 1
    assert '"TEST_VAR" has unknown env "development"' in ret.stdout


def test_validate_empty_string_fails(tmp_path):
    """test empty string validation failure"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  KMS_KEY_ARN: abc

environment_variables:
  TEST_VAR:
    default: ""
""")

    ret = subprocess.run(
        f'{CMD} -f {tmp_path}/envars.yml validate',
        shell=True,
        capture_output=True,
        text=True
    )
    assert ret.returncode == 1
    assert '"TEST_VAR" "default" has unsupported empty string' in ret.stdout


def test_validate_empty_string_in_account_fails(tmp_path):
    """test account specific configs with empty strings"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  KMS_KEY_ARN: abc

environment_variables:
  TEST_VAR:
    prod:
      master: ""
""")

    ret = subprocess.run(
        f'{CMD} -f {tmp_path}/envars.yml validate',
        shell=True,
        capture_output=True,
        text=True
    )
    assert ret.returncode == 1
    assert '"TEST_VAR" "prod" "master" has unsupported empty string' in ret.stdout


def test_validate_invalid_account_fails(tmp_path):
    """test invalid account names"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  KMS_KEY_ARN: abc

environment_variables:
  TEST_VAR:
    prod:
      production: prod-value
""")

    ret = subprocess.run(
        f'{CMD} -f {tmp_path}/envars.yml validate',
        shell=True,
        capture_output=True,
        text=True
    )
    assert ret.returncode == 1
    assert '"TEST_VAR" "prod" has invalid account "production"' in ret.stdout


def test_validate_multiple_errors(tmp_path):
    """Test if we get multiple validation reports"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  KMS_KEY_ARN: abc

environment_variables:
  test_var:
    default: value
  VALID_VAR:
    default: valid
    invalid_env: value
  ANOTHER_VAR:
    prod:
      invalid_account: value
""")

    ret = subprocess.run(
        f'{CMD} -f {tmp_path}/envars.yml validate',
        shell=True,
        capture_output=True,
        text=True
    )
    assert ret.returncode == 1
    assert 'var name "test_var" is not uppercase' in ret.stdout
    assert '"VALID_VAR" has unknown env "invalid_env"' in ret.stdout
    assert '"ANOTHER_VAR" "prod" has invalid account "invalid_account"' in ret.stdout


def test_validate_with_description(tmp_path):
    """test valid description field"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  KMS_KEY_ARN: abc

environment_variables:
  TEST_VAR:
    default: value
    description: This is a test variable
""")

    ret = run_cmd(tmp_path, 'validate')
    assert ret.returncode == 0


def test_validate_complex_valid_config(tmp_path):
    """test validation with a more complex file"""
    run_cmd(tmp_path, 'init --app testapp --environments prod,staging,dev --kms-key-arn abc')

    with open(f'{tmp_path}/envars.yml', 'w') as f:
        f.write("""configuration:
  APP: testapp
  ENVIRONMENTS:
  - prod
  - staging
  - dev
  KMS_KEY_ARN: abc

environment_variables:
  API_KEY:
    default: default-key
    description: API key for external service

  DATABASE_URL:
    dev: dev-db-url
    staging: staging-db-url
    prod:
      master: prod-master-db-url
      sandbox: prod-sandbox-db-url

  FEATURE_FLAG_1:
    default: "false"
    prod: "true"

  MULTI_ACCOUNT_VAR:
    default:
      master: default-master
      sandbox: default-sandbox
    staging:
      master: staging-master
      sandbox: staging-sandbox
""")

    ret = run_cmd(tmp_path, 'validate')
    assert ret.returncode == 0


def test_validate_nonexistent_file(tmp_path):
    """Test validation fails gracefully when file doesn't exist"""
    ret = subprocess.run(
        f'{CMD} -f {tmp_path}/nonexistent.yml validate',
        shell=True,
        capture_output=True,
        text=True
    )
    assert ret.returncode == 1
