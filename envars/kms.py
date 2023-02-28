import base64

import boto3

kms_client = boto3.client('kms')


class KMSAgent(object):

    def __init__(self, kms_key_arn):
        self.cache = {}
        self.kms_key_arn = kms_key_arn

    def reset(self):
        self.cache = {}

    def decrypt(self, base64_ciphertext, encryption_context):
        cipher_blob = base64.b64decode(base64_ciphertext.encode('utf-8'))
        response = kms_client.decrypt(
            CiphertextBlob=cipher_blob,
            EncryptionContext=encryption_context,
        )
        plaintext = response['Plaintext'].decode('utf-8')
        cache_key = self._cache_key(plaintext, encryption_context)
        self.cache[cache_key] = base64_ciphertext
        return plaintext

    def encrypt(self, plaintext, encryption_context):
        cache_key = self._cache_key(plaintext, encryption_context)
        try:
            return self.cache[cache_key]
        except KeyError:
            pass

        response = kms_client.encrypt(
            KeyId=self.kms_key_arn,
            Plaintext=plaintext.encode('utf-8'),
            EncryptionContext=encryption_context
        )
        base64_ciphertext = base64.b64encode(response['CiphertextBlob']).decode('utf-8')
        self.cache[cache_key] = base64_ciphertext
        return "\n".join([base64_ciphertext[i:i + 80] for i in range(0, len(base64_ciphertext), 80)])

    def _cache_key(self, plaintext, encryption_context):
        return (plaintext,) + tuple(sorted(encryption_context.items()))
