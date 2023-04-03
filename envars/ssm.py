import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

try:
    ssm_client = boto3.client('ssm')
except (ProfileNotFound, NoCredentialsError):
    print('AWS credentials not found, is AWS_PROFILE set? does "~/.aws/credentials" exist?')
    sys.exit(1)


class SsmAgent(object):

    def fetch(self, name):
        value = 'UNKNOWN-ERROR-FETCHING-FROM-PARAMETER-STORE'
        try:
            param = ssm_client.get_parameter(Name=name, WithDecryption=True)
            value = param['Parameter']['Value']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                value = f'NOT-FOUND-IN-PSTORE-{name}'
            elif e.response['Error']['Code'] == 'AccessDeniedException':
                value = f'PARAMETER-STORE-ACCESS-DENIED-{name}'
        return value
