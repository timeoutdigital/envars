import sys
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

# Configure logging for the module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Default logging level

class SsmAgent:
    """
    A class to interact with AWS Systems Manager Parameter Store.
    """

    def __init__(self, ssm_client: Optional[boto3.client] = None):
        """
        Initializes the SsmAgent with an SSM client.

        Args:
            ssm_client: An optional pre-initialized boto3 SSM client.
                        If not provided, a new client will be created.
        """
        if ssm_client:
            self.ssm_client = ssm_client
        else:
            try:
                self.ssm_client = boto3.client('ssm')
            except (ProfileNotFound, NoCredentialsError):
                logger.error(
                    "AWS credentials not found. "
                    "Please ensure AWS_PROFILE is set or ~/.aws/credentials exists."
                )
                sys.exit(1)
            except Exception as e:
                logger.error(f"Failed to initialize SSM client: {e}")
                sys.exit(1)

    def fetch(self, name: str) -> str:
        """
        Fetches a parameter from AWS Systems Manager Parameter Store.

        Args:
            name: The name of the parameter to fetch.

        Returns:
            The value of the parameter. Returns a specific error string
            if the parameter is not found or access is denied.
        """
        try:
            param = self.ssm_client.get_parameter(Name=name, WithDecryption=True)
            return param['Parameter']['Value']
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'ParameterNotFound':
                logger.warning(f"Parameter '{name}' not found in Parameter Store.")
                return f'NOT-FOUND-IN-PSTORE-{name}'
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied to parameter '{name}' in Parameter Store.")
                return f'PARAMETER-STORE-ACCESS-DENIED-{name}'
            else:
                logger.error(f"An unexpected AWS client error occurred: {e}")
                return f'UNKNOWN-AWS-ERROR-FETCHING-FROM-PARAMETER-STORE-{name}'
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching parameter '{name}': {e}")
            return f'UNKNOWN-ERROR-FETCHING-FROM-PARAMETER-STORE-{name}'


