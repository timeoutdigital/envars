import logging
import re
import os
from typing import Dict, Any, List, Optional, Union, cast

import jinja2
import yaml

# Suppress boto3/botocore logging to avoid excessive output
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Default logging level

class Secret:
    """
    A custom YAML tag for representing secret values.
    When dumped, it will be represented as !secret <value>.
    When loaded, it will create a Secret object.
    """
    def __init__(self, value: str):
        self.value = value

    def __repr__(self) -> str:
        return f"Secret(value='{self.value}')"

    def __str__(self) -> str:
        return self.value

def secret_representer(dumper: yaml.Dumper, data: Secret) -> yaml.ScalarNode:
    """YAML representer for the Secret class."""
    return dumper.represent_scalar(u'!secret', u'%s' % data.value, style='|')

def secret_constructor(loader: yaml.Loader, node: yaml.nodes.MappingNode) -> Secret:
    """YAML constructor for the Secret class."""
    return Secret(loader.construct_scalar(node))

# Add the representer and constructor to PyYAML
yaml.add_representer(Secret, secret_representer)
yaml.add_constructor(u'!secret', secret_constructor)


# Define get_loader here, before EnVars class uses it
def get_loader():
    """
    Returns a YAML SafeLoader configured with the custom Secret constructor.
    """
    loader = yaml.SafeLoader
    loader.add_constructor(u'!secret', secret_constructor)
    return loader


class EnVar:
    """
    Represents a single environment variable with values for different environments and accounts.
    """
    def __init__(
        self,
        parent: 'EnVars', # Forward reference for type hinting
        name: str,
        envs: Dict[str, Any],
        app: str,
        desc: Optional[str] = None
    ):
        logger.debug(f'EnVar init(name={name}, envs={envs}, app={app}, desc={desc})')
        self.parent = parent
        self.app = app
        self.desc = desc
        self.envs = envs
        if self.desc:
            self.envs['description'] = self.desc # Store description within envs for YAML output
        self.name = name

    def __repr__(self) -> str:
        return f"EnVar(name='{self.name}', envs={self.envs})"

    def get_value(
        self,
        env: str,
        account: Optional[str],
        decrypt: bool = False,
        fetch_pstore: bool = False
    ) -> Optional[Union[str, Secret]]:
        """
        Retrieves the value of the environment variable for a given environment and account.

        Args:
            env: The environment name (e.g., 'dev', 'prod').
            account: The AWS account name (e.g., 'master', 'sandbox').
            decrypt: Whether to decrypt secret values using KMS.
            fetch_pstore: Whether to fetch values from Parameter Store if specified.

        Returns:
            The environment variable's value, which can be a string or a Secret object.
        """
        value: Optional[Union[str, Secret]] = None

        # Try to get value from specific environment
        if env in self.envs:
            env_value = self.envs[env]
            if isinstance(env_value, dict):
                if account and account in env_value:
                    value = self._decrypt_if_secret(env_value[account], env, account, decrypt)
            else:
                value = self._decrypt_if_secret(env_value, env, None, decrypt)

        # If not found, try to get value from 'default' environment
        if value is None and 'default' in self.envs:
            default_value = self.envs['default']
            if isinstance(default_value, dict):
                if account and account in default_value:
                    value = self._decrypt_if_secret(default_value[account], 'default', account, decrypt)
            else:
                value = self._decrypt_if_secret(default_value, 'default', None, decrypt)

        # Fetch from Parameter Store if requested and not a Secret
        if value and fetch_pstore and not isinstance(value, Secret):
            str_value = str(value) # Cast to string for 'parameter_store:' check
            if str_value.startswith('parameter_store:'):
                from .ssm import SsmAgent # Lazy import to avoid circular dependency
                ssm_agent = SsmAgent()
                pname_template = str_value.split(':', 1)[1]
                jenv = jinja2.Environment()
                # Render template with current environment (STAGE)
                pname = jenv.from_string(pname_template).render({'STAGE': env})
                value = ssm_agent.fetch(pname)
                logger.debug(f"Fetched '{pname}' from Parameter Store: {value}")

        return value

    def _decrypt_if_secret(
        self,
        value: Any,
        env: str,
        account: Optional[str],
        decrypt: bool
    ) -> Union[str, Secret]:
        """Helper to decrypt a Secret value if decrypt is True."""
        logger.debug(f'Attempting to decrypt value: {value}, env: {env}, account: {account}, decrypt: {decrypt}')
        if decrypt and isinstance(value, Secret):
            from .kms import KMSAgent # Lazy import
            if not self.parent.kms_key_arn:
                raise ValueError("KMS_KEY_ARN is not configured in EnVars for decryption.")

            kms_agent = KMSAgent(self.parent.kms_key_arn)
            encryption_context: Dict[str, str] = {'app': self.app}
            if env != 'default':
                encryption_context['env'] = env
            if account:
                encryption_context['account'] = account
            logger.debug(f'Encryption context for decryption: {encryption_context}')
            try:
                decrypted_value = kms_agent.decrypt(value.value, encryption_context)
                return decrypted_value
            except Exception as e:
                logger.error(f"Failed to decrypt secret for {self.name} in {env}/{account}: {e}")
                return f"DECRYPTION-FAILED-{self.name}" # Return a clear error message
        return value


class EnVars:
    """
    Manages a collection of environment variables loaded from and saved to a YAML file.
    """
    def __init__(self, filename: str = 'envars.yml'):
        self.filename = filename
        self.app: Optional[str] = None
        self.envs: List[str] = []
        self.envars: List[EnVar] = []
        self.kms_key_arn: Optional[str] = None

    def load(self) -> None:
        """
        Loads environment variables and configuration from the YAML file.
        """
        try:
            with open(self.filename, "rb") as envars_yml:
                # Corrected: Call get_loader() to get the loader instance
                envars_file = yaml.load(envars_yml, Loader=get_loader())

            if not isinstance(envars_file, dict):
                raise ValueError(f"Invalid YAML file format in {self.filename}: Expected a dictionary.")

            config = envars_file.get("configuration", {})
            self.app = config.get('APP')
            self.kms_key_arn = config.get('KMS_KEY_ARN')
            self.envs = config.get('ENVIRONMENTS', [])

            if not self.app or not self.kms_key_arn or not self.envs:
                logger.warning(
                    f"Missing configuration in {self.filename}. "
                    "Ensure 'APP', 'KMS_KEY_ARN', and 'ENVIRONMENTS' are defined."
                )

            environment_variables = envars_file.get('environment_variables', {})
            self.envars = [] # Clear existing envars before loading
            for var_name, var_data in environment_variables.items():
                desc = var_data.pop('description', None) # Extract description if present
                self.envars.append(EnVar(self, var_name, var_data, self.app, desc=desc))
            logger.info(f"Successfully loaded environment variables from {self.filename}")

        except FileNotFoundError:
            logger.error(f"EnVars file not found: {self.filename}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {self.filename}: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading {self.filename}: {e}")
            raise

    def save(self) -> None:
        """
        Saves the current environment variables and configuration to the YAML file.
        """
        try:
            with open(self.filename, "w") as envars_yml:
                # Dump configuration section
                config_data: Dict[str, Any] = {
                    'configuration': {
                        'APP': self.app,
                        'ENVIRONMENTS': self.envs,
                        'KMS_KEY_ARN': self.kms_key_arn,
                    }
                }
                # Use default_flow_style=False for block style YAML
                stream = yaml.dump(config_data, default_flow_style=False, sort_keys=False)
                # Add extra newlines for better readability between sections
                envars_yml.write(re.sub(r'\n  ([A-Z])', r'\n\n  \1', stream))
                envars_yml.write('\n')

                # Dump environment variables section
                env_vars_data: Dict[str, Any] = {
                    'environment_variables': self._build_yaml_envars()
                }
                stream = yaml.dump(env_vars_data, default_flow_style=False, sort_keys=False)
                envars_yml.write(re.sub(r'\n  ([A-Z])', r'\n\n  \1', stream))
            logger.info(f"Successfully saved environment variables to {self.filename}")
        except Exception as e:
            logger.error(f"Failed to save environment variables to {self.filename}: {e}")
            raise

    def add(
        self,
        name: str,
        value: str,
        env_name: str = 'default',
        account: Optional[str] = None,
        desc: Optional[str] = None,
        is_secret: bool = False
    ) -> None:
        """
        Adds or updates an environment variable.

        Args:
            name: The name of the environment variable.
            value: The value of the environment variable.
            env_name: The environment to which the variable belongs (e.g., 'dev', 'prod').
            account: The AWS account to which the variable belongs (e.g., 'master', 'sandbox').
            desc: An optional description for the variable.
            is_secret: True if the value should be encrypted as a secret.
        """
        logger.debug(f'add(name={name}, value={value}, env_name={env_name}, account={account}, desc={desc}, is_secret={is_secret})')

        if env_name != 'default' and env_name not in self.envs:
            raise ValueError(f'Unknown environment: "{env_name}". Please add it to ENVIRONMENTS in config.')

        if account and account not in ['master', 'sandbox']:
            raise ValueError(f'Unknown account: "{account}". Must be "master" or "sandbox".')

        processed_value: Union[str, Secret] = value
        if is_secret:
            from .kms import KMSAgent # Lazy import
            if not self.kms_key_arn:
                raise ValueError("KMS_KEY_ARN is not configured in EnVars for encryption.")

            kms_agent = KMSAgent(self.kms_key_arn)
            encryption_context: Dict[str, str] = {'app': self.app or 'unknown_app'} # Provide a default if app is not set
            if env_name != 'default':
                encryption_context['env'] = env_name
            if account:
                encryption_context['account'] = account
            logger.debug(f'Encryption context for encryption: {encryption_context}')
            try:
                encrypted_value = kms_agent.encrypt(value, encryption_context)
                processed_value = Secret(encrypted_value)
            except Exception as e:
                logger.error(f"Failed to encrypt value for {name} in {env_name}/{account}: {e}")
                raise RuntimeError(f"Encryption failed for {name}.") from e

        # Find existing EnVar or create a new one
        existing_envar: Optional[EnVar] = next((v for v in self.envars if v.name == name), None)

        if existing_envar:
            if desc:
                existing_envar.desc = desc
                existing_envar.envs['description'] = desc # Update description in envs dict

            if account:
                if env_name not in existing_envar.envs or not isinstance(existing_envar.envs[env_name], dict):
                    existing_envar.envs[env_name] = {} # Initialize as dict if not already
                existing_envar.envs[env_name][account] = processed_value
            else:
                existing_envar.envs[env_name] = processed_value
            logger.info(f"Updated variable '{name}' for env '{env_name}' (account: {account or 'N/A'}).")
        else:
            new_envs: Dict[str, Any] = {}
            if account:
                new_envs[env_name] = {account: processed_value}
            else:
                new_envs[env_name] = processed_value
            self.envars.append(EnVar(self, name, new_envs, self.app or 'unknown_app', desc=desc))
            logger.info(f"Added new variable '{name}' for env '{env_name}' (account: {account or 'N/A'}).")

    def _build_yaml_envars(self) -> Dict[str, Any]:
        """Helper to build a dictionary suitable for YAML dumping of environment variables."""
        envars_data: Dict[str, Any] = {}
        for var in self.envars:
            # Create a copy to avoid modifying the original EnVar's envs dict
            # when popping 'description' for YAML output
            var_envs_copy = var.envs.copy()
            if var.desc:
                # Ensure description is at the top for readability in YAML
                envars_data[var.name] = {'description': var.desc, **var_envs_copy}
            else:
                envars_data[var.name] = var_envs_copy
        return envars_data

    def get_var(self, var_name: str, env: str, account: Optional[str]) -> Dict[str, Any]:
        """
        Retrieves a single environment variable's value.

        Args:
            var_name: The name of the variable to retrieve.
            env: The environment name.
            account: The AWS account name.

        Returns:
            A dictionary containing the variable name and its resolved value.
        """
        for v in self.envars:
            if v.name == var_name:
                resolved_value = v.get_value(env, account, fetch_pstore=True)
                return {v.name: resolved_value}
        logger.warning(f"Variable '{var_name}' not found.")
        return {}

    def build_env(
        self,
        env: str,
        account: str,
        decrypt: bool = False,
        template_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Builds a dictionary of environment variables for a given environment and account,
        resolving secrets and parameter store values, and processing Jinja templates.

        Args:
            env: The environment name.
            account: The AWS account name.
            decrypt: Whether to decrypt secret values.
            template_vars: Additional variables to use for Jinja templating.

        Returns:
            A dictionary of resolved environment variables.
        """
        logger.debug(f'build_env(env={env}, account={account}, decrypt={decrypt}, template_vars={template_vars})')
        resolved_envars: Dict[str, str] = {}
        current_template_vars: Dict[str, str] = template_vars.copy() if template_vars else {}

        # Ensure essential template variables are present
        current_template_vars['STAGE'] = env
        current_template_vars['AWS_ACCOUNT_ID'] = account # Add account to template vars
        if 'RELEASE_SHA' in os.environ:
            current_template_vars['RELEASE'] = os.environ.get('RELEASE_SHA')
        if 'AWS_REGION' in os.environ:
            current_template_vars['AWS_REGION'] = os.environ.get('AWS_REGION')
        if 'AWS_ACCOUNT_ID' in os.environ: # Redundant check but good for clarity
            current_template_vars['AWS_ACCOUNT_ID'] = os.environ.get('AWS_ACCOUNT_ID', account)


        # First pass: Fetch all non-secret values and populate initial template_vars
        for var_obj in self.envars:
            value = var_obj.get_value(env, account, decrypt=False, fetch_pstore=True)
            if value is not None and not isinstance(value, Secret):
                str_value = str(value)
                if var_obj.name not in current_template_vars:
                    current_template_vars[var_obj.name] = str_value
                resolved_envars[var_obj.name] = str_value

        jenv = jinja2.Environment()

        # Process Jinja templates for non-secret values
        for name, value in resolved_envars.items():
            try:
                resolved_envars[name] = jenv.from_string(value).render(current_template_vars)
                # Update current_template_vars with resolved value for subsequent templates
                current_template_vars[name] = resolved_envars[name]
            except jinja2.exceptions.TemplateError as e:
                logger.error(f"Jinja templating error for variable '{name}': {e}")
                resolved_envars[name] = f"TEMPLATE-ERROR-{name}"

        # Second pass: Fetch secrets (which might depend on template_vars resolved in first pass)
        for var_obj in self.envars:
            if isinstance(var_obj.get_value(env, account, decrypt=False, fetch_pstore=False), Secret):
                # We need to re-evaluate the value with decryption and potentially updated template_vars
                value = var_obj.get_value(env, account, decrypt=decrypt, fetch_pstore=True)
                if value is not None:
                    resolved_envars[var_obj.name] = str(value) # Ensure it's a string

        return resolved_envars

    def build_all_envs_for_account(self, account: str, var: Optional[str] = None, decrypt: bool = False) -> Dict[str, Any]:
        """
        Builds a dictionary of all environment variables and their configurations
        for a given account, optionally filtering by variable name.

        Args:
            account: The AWS account name.
            var: Optional. If provided, only build data for this specific variable.
            decrypt: Whether to decrypt secret values when building the full structure.

        Returns:
            A dictionary where keys are variable names and values are their
            environment-specific configurations.
        """
        logger.debug(f'build_all_envs_for_account(account={account}, var={var}, decrypt={decrypt})')
        all_envars_config: Dict[str, Any] = {}
        for envar_obj in self.envars:
            if var and envar_obj.name != var:
                continue

            # This part needs careful consideration:
            # The original `build` method in `EnVars` just returned `var.envs`.
            # If `decrypt=True` is passed here, it implies we want to see decrypted
            # values in the *output structure*, not just for `build_env`.
            # This would require iterating through `envar_obj.envs` and applying
            # decryption where `isinstance(value, Secret)`.

            processed_envs: Dict[str, Any] = {}
            for env_key, env_val in envar_obj.envs.items():
                if env_key == 'description':
                    processed_envs[env_key] = env_val
                    continue

                if isinstance(env_val, dict): # Account-specific values
                    processed_account_values: Dict[str, Any] = {}
                    for acc_key, acc_val in env_val.items():
                        processed_account_values[acc_key] = envar_obj._decrypt_if_secret(acc_val, env_key, acc_key, decrypt)
                    processed_envs[env_key] = processed_account_values
                else: # Environment-specific value
                    processed_envs[env_key] = envar_obj._decrypt_if_secret(env_val, env_key, None, decrypt)

            all_envars_config[envar_obj.name] = processed_envs
        return all_envars_config

    def print_env_config(self, account: str, env: Optional[str] = None, var: Optional[str] = None, decrypt: bool = False) -> str:
        """
        Prints the environment variable configuration in YAML format.

        Args:
            account: The AWS account name.
            env: Optional. If provided, filters by this environment. (Note: original `print` didn't use `env` filter directly for full dump)
            var: Optional. If provided, filters by this specific variable.
            decrypt: Whether to decrypt secret values in the output.

        Returns:
            A YAML formatted string of the environment variables.
        """
        logger.debug(f'print_env_config(account={account}, env={env}, var={var}, decrypt={decrypt})')
        # The original `print` method called `build` which returned the full structure.
        # If `env` is provided, the behavior needs to be clarified.
        # For now, it will dump the full configuration, optionally filtered by `var`.
        # If the user wants `build_env` output, they should use `build_env` directly.
        data_to_print = self.build_all_envs_for_account(account, var, decrypt)
        return yaml.dump(data_to_print, default_flow_style=False, sort_keys=False)


