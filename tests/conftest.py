import pytest
from botocore.stub import Stubber

from envars.kms import kms_client


@pytest.fixture(scope='function', autouse=True)
def kms_stub():
    with Stubber(kms_client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()
