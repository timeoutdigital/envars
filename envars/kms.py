import base64
import logging
from typing import Dict, Any, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

# Configure logging for the module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Default logging level

class KMSAgent:
    """
    A class to interact with AWS Key Management Service (KMS) for encryption and decryption.
    """

    def __init__(self, kms_key_arn: str, kms_client: Optional[boto3.client] = None):
        """
        Initializes the KMSAgent with a KMS key ARN and an optional KMS client.

        Args:
            kms_key_arn: The ARN of the KMS key to use for encryption/decryption.
            kms_client: An optional pre-initialized boto3 KMS client.
                        If not provided, a new client will be created.
        """
        self.cache: Dict[Tuple[Any, ...], str] = {}
        self.kms_key_arn = kms_key_arn
        if kms_client:
            self.kms_client = kms_client
        else:
            try:
                self.kms_client = boto3.client('kms')
            except (ProfileNotFound, NoCredentialsError):
                logger.error(
                    "AWS credentials not found. "
                    "Please ensure AWS_PROFILE is set or ~/.aws/credentials exists."
                )
                sys.exit(1) # Exit since KMS operations are critical
            except Exception as e:
                logger.error(f"Failed to initialize KMS client: {e}")
                sys.exit(1) # Exit since KMS operations are critical

    def reset_cache(self) -> None:
        """Resets the internal cache."""
        self.cache = {}
        logger.debug("KMSAgent cache reset.")

    def decrypt(self, base64_ciphertext: str, encryption_context: Dict[str, str]) -> str:
        """
        Decrypts a base64 encoded ciphertext using KMS.

        Args:
            base64_ciphertext: The base64 encoded ciphertext to decrypt.
            encryption_context: The encryption context used during encryption.

        Returns:
            The plaintext string.
        """
        try:
            cipher_blob = base64.b64decode(base64_ciphertext.encode('utf-8'))
            response = self.kms_client.decrypt(
                CiphertextBlob=cipher_blob,
                EncryptionContext=encryption_context,
            )
            plaintext = response['Plaintext'].decode('utf-8')
            cache_key = self._generate_cache_key(plaintext, encryption_context)
            self.cache[cache_key] = base64_ciphertext # Cache the original ciphertext
            logger.debug("Successfully decrypted ciphertext.")
            return plaintext
        except ClientError as e:
            logger.error(f"KMS decryption failed: {e}")
            raise RuntimeError(f"KMS decryption failed: {e}") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during decryption: {e}")
            raise RuntimeError(f"Unexpected decryption error: {e}") from e

    def encrypt(self, plaintext: str, encryption_context: Dict[str, str]) -> str:
        """
        Encrypts a plaintext string using KMS.

        Args:
            plaintext: The string to encrypt.
            encryption_context: The encryption context to associate with the ciphertext.

        Returns:
            The base64 encoded ciphertext.
        """
        cache_key = self._generate_cache_key(plaintext, encryption_context)
        if cache_key in self.cache:
            logger.debug("Returning encrypted value from cache.")
            return self.cache[cache_key]

        try:
            response = self.kms_client.encrypt(
                KeyId=self.kms_key_arn,
                Plaintext=plaintext.encode('utf-8'),
                EncryptionContext=encryption_context
            )
            base64_ciphertext = base64.b64encode(response['CiphertextBlob']).decode('utf-8')
            self.cache[cache_key] = base64_ciphertext
            logger.debug("Successfully encrypted plaintext and cached result.")
            # Format the output to be wrapped at 80 characters for readability in YAML
            return "\n".join([base64_ciphertext[i:i + 80] for i in range(0, len(base64_ciphertext), 80)])
        except ClientError as e:
            logger.error(f"KMS encryption failed: {e}")
            raise RuntimeError(f"KMS encryption failed: {e}") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during encryption: {e}")
            raise RuntimeError(f"Unexpected encryption error: {e}") from e

    def _generate_cache_key(self, plaintext: str, encryption_context: Dict[str, str]) -> Tuple[Any, ...]:
        """
        Generates a cache key from plaintext and encryption context.

        Args:
            plaintext: The plaintext string.
            encryption_context: The encryption context dictionary.

        Returns:
            A tuple representing the cache key.
        """
        # Sort the encryption context items to ensure consistent cache keys
        return (plaintext,) + tuple(sorted(encryption_context.items()))


