#!/usr/bin/env python3
import argparse
import logging
import os
import re
import subprocess
import sys
from typing import List, Dict, Any, Optional, Iterable, Union

import boto3
import yaml

# Assuming models.py is in the same package/directory
from .models import EnVars, Secret

# Configure logging for the main script
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Default logging level, can be changed by --debug

class EnvarsCLI:
    """
    Command-line interface for managing environment variables using EnVars.
    """
    def __init__(self):
        self.parser = self._setup_argument_parser()

    def _setup_argument_parser(self) -> argparse.ArgumentParser:
        """Sets up the argument parser for the CLI."""
        parser = argparse.ArgumentParser(
            description='Environment Management Tool',
            formatter_class=argparse.RawTextHelpFormatter # Preserve formatting for help messages
        )
        parser.add_argument(
            '-f',
            '--filename',
            default='envars.yml',
            help='Path to the environment variables YAML file (default: envars.yml).'
        )
        parser.add_argument(
            '-d',
            '--debug',
            action='store_true',
            help='Enable debug logging.'
        )

        subparsers = parser.add_subparsers(
            title="commands",
            dest="command", # Make command name accessible
            help="Available commands"
        )

        # Init subparser
        parser_init = subparsers.add_parser(
            'init',
            help='Initialize a new envars YAML file.',
            description='Initializes a new envars YAML file with basic configuration.'
        )
        parser_init.add_argument(
            '-a',
            '--app',
            required=True,
            help='The application name.'
        )
        parser_init.add_argument(
            '-e',
            '--environments',
            required=True,
            help='Comma-separated list of environments (e.g., dev,prod,staging).'
        )
        parser_init.add_argument(
            '-k',
            '--kms-key-arn',
            required=True,
            help='The AWS KMS Key ARN for encrypting/decrypting secrets.'
        )
        parser_init.set_defaults(func=self._init_envar_file)

        # Add subparser
        parser_add = subparsers.add_parser(
            'add',
            help='Add or update an environment variable.',
            description='Adds a new environment variable or updates an existing one.'
        )
        parser_add.add_argument(
            '-a',
            '--account',
            required=False,
            default=None,
            choices=['master', 'sandbox'],
            help='Specify AWS account (master or sandbox) if variable is account-specific.'
        )
        parser_add.add_argument(
            '-D', # Changed from -d to avoid conflict with --debug
            '--desc',
            required=False,
            help='A short description for the variable.'
        )
        parser_add.add_argument(
            '-e',
            '--env',
            required=False,
            default='default',
            help='The environment for the variable (default: default).'
        )
        parser_add.add_argument(
            '-s',
            '--secret',
            required=False,
            action='store_true',
            help='Mark the variable as a secret (will be KMS encrypted).'
        )
        parser_add.add_argument(
            'variable',
            help='Variable in "VAR_NAME=value" format (e.g., MY_VAR=my_value).'
        )
        parser_add.set_defaults(func=self._add_variable)

        # Print subparser
        parser_print = subparsers.add_parser(
            'print',
            help='Print environment variables.',
            description='Prints environment variables, optionally filtered and decrypted.'
        )
        parser_print.add_argument(
            '-a',
            '--account',
            required=False,
            default=None,
            help='Specify AWS account to resolve values (e.g., master, sandbox).'
        )
        parser_print.add_argument(
            '-d',
            '--decrypt',
            required=False,
            action='store_true',
            help='Decrypt secret variables before printing.'
        )
        parser_print.add_argument(
            '-e',
            '--env',
            required=False,
            help='Specify environment to resolve values (e.g., dev, prod). Required for --yaml and non-var specific output.'
        )
        parser_print.add_argument(
            '-n',
            '--no-check-env',
            action='store_true',
            help='Do not check if the specified environment exists in the config.'
        )
        parser_print.add_argument(
            '-t',
            '--template-var',
            required=False,
            nargs='+',
            action='append',
            default=[],
            help='Additional template variables in "KEY=VALUE" format.'
        )
        parser_print.add_argument(
            '-v',
            '--var',
            required=False,
            default=None,
            help='Print only a specific variable (case-insensitive match).'
        )
        parser_print.add_argument(
            '-y',
            '--yaml',
            required=False,
            action='store_true',
            help='Output variables in YAML format. Requires --env.'
        )
        parser_print.add_argument(
            '-q',
            '--quote',
            required=False,
            action='store_true',
            help='Quote variable values (e.g., VAR=\'value\'). Only for non-YAML output.'
        )
        parser_print.set_defaults(func=self._print_env_vars)

        # Execute subparser
        parser_exec = subparsers.add_parser(
            'exec',
            help='Execute a command with environment variables set.',
            description='Executes a shell command after setting environment variables from the envars file.'
        )
        parser_exec.add_argument(
            '-e',
            '--env',
            required=False,
            help='Specify environment to resolve values (e.g., dev, prod). If not provided, uses STAGE env var.'
        )
        parser_exec.add_argument(
            '-n',
            '--no-check-env',
            action='store_true',
            help='Do not check if the specified environment exists in the config.'
        )
        parser_exec.add_argument(
            '-v',
            '--var',
            required=False,
            default=None,
            help='Set only a specific variable for the command.'
        )
        parser_exec.add_argument(
            '-a',
            '--account',
            required=False,
            default=None,
            help='Specify AWS account to resolve values (e.g., master, sandbox).'
        )
        parser_exec.add_argument(
            '-t',
            '--template-var',
            required=False,
            nargs='+',
            action='append',
            default=[],
            help='Additional template variables in "KEY=VALUE" format.'
        )
        parser_exec.add_argument(
            'command',
            nargs=argparse.REMAINDER,
            help='The command and its arguments to execute.'
        )
        parser_exec.set_defaults(func=self._execute_command)

        # Set SystemD Env subparser
        parser_set_systemd_env = subparsers.add_parser(
            'set-systemd-env',
            help='Set environment variables for SystemD.',
            description='Sets environment variables using `systemctl set-environment` for SystemD services.'
        )
        parser_set_systemd_env.add_argument(
            '-e',
            '--env',
            required=False,
            help='Specify environment to resolve values (e.g., dev, prod). If not provided, uses STAGE env var.'
        )
        parser_set_systemd_env.add_argument(
            '-n',
            '--no-check-env',
            action='store_true',
            help='Do not check if the specified environment exists in the config.'
        )
        parser_set_systemd_env.add_argument(
            '-v',
            '--var',
            required=False,
            default=None,
            help='Set only a specific variable for SystemD.'
        )
        parser_set_systemd_env.add_argument(
            '-a',
            '--account',
            required=False,
            default=None,
            help='Specify AWS account to resolve values (e.g., master, sandbox).'
        )
        parser_set_systemd_env.add_argument(
            '-t',
            '--template-var',
            required=False,
            nargs='+',
            action='append',
            default=[],
            help='Additional template variables in "KEY=VALUE" format.'
        )
        parser_set_systemd_env.set_defaults(func=self._set_systemd_environment)

        # Validate subparser
        parser_validate = subparsers.add_parser(
            'validate',
            help='Validate the envars YAML file.',
            description='Checks the envars file for common configuration errors and inconsistencies.'
        )
        parser_validate.set_defaults(func=self._validate_envars_file)

        return parser

    def run(self) -> None:
        """Parses arguments and executes the corresponding function."""
        args = self.parser.parse_args()

        if args.debug:
            logger.setLevel(logging.DEBUG)
            logging.getLogger('boto3').setLevel(logging.DEBUG)
            logging.getLogger('botocore').setLevel(logging.DEBUG)

        # If no command is provided, print help and exit
        if not hasattr(args, 'func'):
            self.parser.print_help()
            sys.exit(0)

        try:
            args.func(args)
        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=args.debug)
            sys.exit(1)

    def _init_envar_file(self, args: argparse.Namespace) -> None:
        """Initializes a new envars YAML file."""
        envars = EnVars(args.filename)
        envars.app = args.app
        envars.kms_key_arn = args.kms_key_arn
        envars.envs = args.environments.split(',')
        envars.save()
        logger.info(f"Initialized new envars file: {args.filename}")

    def _add_variable(self, args: argparse.Namespace) -> None:
        """Adds or updates an environment variable."""
        matches = re.match(r'^([A-Z][A-Z0-9_]+)=(.*)$', args.variable)
        if not matches:
            raise ValueError('"VAR_NAME=value" format expected (e.g., MY_VAR=my_value). Variable name must be uppercase alphanumeric with underscores, starting with a letter.')
        name = matches.group(1)
        value = matches.group(2)

        envars = EnVars(args.filename)
        envars.load() # Load existing data
        envars.add(
            name,
            value,
            env_name=args.env,
            account=args.account,
            desc=args.desc,
            is_secret=args.secret,
        )
        envars.save() # Save changes
        logger.info(f"Variable '{name}' added/updated in {args.filename}.")
        # Optionally print the added variable's resolved value
        # For 'add' command, it's often useful to see what was just added
        # print(envars.print_env_config(args.account, env=args.env, var=name, decrypt=True))


    def _print_env_vars(self, args: argparse.Namespace) -> None:
        """Prints environment variables based on arguments."""
        # Normalize template_var to a single list of "KEY=VALUE" strings
        template_vars_flat = self._flatten_template_vars(args.template_var)
        template_vars_dict = {
            k: v for k, v in (item.split('=', 1) for item in template_vars_flat if '=' in item)
        }

        envars = EnVars(args.filename)
        envars.load()

        if not args.no_check_env and args.env and args.env not in envars.envs:
            raise ValueError(f'Unknown environment: "{args.env}". Please add it to ENVIRONMENTS in config or use --no-check-env.')

        account = args.account if args.account else self._get_aws_account()

        if args.env:
            # If --env is specified, we build the environment for execution/export
            resolved_env_vars = envars.build_env(
                args.env,
                account,
                decrypt=args.decrypt,
                template_vars=template_vars_dict
            )
            if args.yaml:
                print(yaml.dump({'envars': resolved_env_vars}, default_flow_style=False, sort_keys=False))
            else:
                for name, value in resolved_env_vars.items():
                    if args.quote:
                        print(f"{name}='{value}'")
                    else:
                        print(f"{name}={value}")
        else:
            # If no --env, print the full configuration structure (or a single var if --var)
            # The original `print` function in models.py implicitly handled this.
            # We call `print_env_config` which gives a YAML dump of the structure.
            # If a single variable is requested, models.py's `get_var` is better.
            if args.var:
                # If only a specific var is requested without an env, we can't fully resolve it
                # as templating/pstore fetches need an env. So we just show its config.
                # This might need clarification on desired behavior.
                # For now, if --var is used without --env, it shows the raw config for that var.
                var_config = envars.get_var(args.var.upper(), "default", account) # Use default env for config view
                if var_config:
                    print(yaml.dump(var_config, default_flow_style=False, sort_keys=False))
                else:
                    logger.warning(f"Variable '{args.var}' not found in {args.filename}.")
            else:
                # Print the entire structure of environment variables
                print(envars.print_env_config(account, decrypt=args.decrypt))


    def _execute_command(self, args: argparse.Namespace) -> None:
        """Executes a command with environment variables set."""
        if not args.command:
            raise ValueError("No command provided to execute.")

        # Determine environment
        env = args.env if args.env else os.environ.get('STAGE')
        if not env:
            raise ValueError('Environment not specified. Use -e <env> or set STAGE environment variable.')

        # Normalize template_var
        template_vars_flat = self._flatten_template_vars(args.template_var)
        template_vars_dict = {
            k: v for k, v in (item.split('=', 1) for item in template_vars_flat if '=' in item)
        }

        envars = EnVars(args.filename)
        envars.load()

        if not args.no_check_env and env not in envars.envs:
            raise ValueError(f'Unknown environment: "{env}". Please add it to ENVIRONMENTS in config or use --no-check-env.')

        account = args.account if args.account else self._get_aws_account()

        resolved_env_vars: Dict[str, str] = {}
        if args.var:
            # If a specific variable is requested, only get that one
            var_data = envars.get_var(args.var.upper(), env, account)
            if not var_data:
                raise ValueError(f"Variable '{args.var}' not found or could not be resolved for env '{env}' and account '{account}'.")
            # get_var returns {VAR_NAME: value}, so extract the value
            resolved_env_vars = {name: str(value) for name, value in var_data.items()}
        else:
            # Otherwise, build all environment variables
            resolved_env_vars = envars.build_env(
                env,
                account,
                decrypt=True, # Always decrypt for execution
                template_vars=template_vars_dict
            )

        # Update current process environment
        os.environ.update(resolved_env_vars)
        logger.debug(f"Executing command: {' '.join(args.command)} with updated environment.")

        # Replace current process with the new command
        # This is generally preferred for exec-like behavior as it avoids creating a new process
        # and correctly handles signals.
        try:
            os.execlp(args.command[0], *args.command)
        except FileNotFoundError:
            logger.error(f"Command not found: {args.command[0]}")
            sys.exit(127) # Standard exit code for command not found
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            sys.exit(1)


    def _set_systemd_environment(self, args: argparse.Namespace) -> None:
        """Sets environment variables for SystemD services."""
        # Determine environment
        env = args.env if args.env else os.environ.get('STAGE')
        if not env:
            raise ValueError('Environment not specified. Use -e <env> or set STAGE environment variable.')

        # Normalize template_var
        template_vars_flat = self._flatten_template_vars(args.template_var)
        template_vars_dict = {
            k: v for k, v in (item.split('=', 1) for item in template_vars_flat if '=' in item)
        }

        envars = EnVars(args.filename)
        envars.load()

        if not args.no_check_env and env not in envars.envs:
            raise ValueError(f'Unknown environment: "{env}". Please add it to ENVIRONMENTS in config or use --no-check-env.')

        account = args.account if args.account else self._get_aws_account()

        resolved_env_vars: Dict[str, str] = {}
        if args.var:
            var_data = envars.get_var(args.var.upper(), env, account)
            if not var_data:
                raise ValueError(f"Variable '{args.var}' not found or could not be resolved for env '{env}' and account '{account}'.")
            resolved_env_vars = {name: str(value) for name, value in var_data.items()}
        else:
            resolved_env_vars = envars.build_env(
                env,
                account,
                decrypt=True, # Always decrypt for SystemD
                template_vars=template_vars_dict
            )

        for name, value in resolved_env_vars.items():
            try:
                # Use a list for subprocess.run to avoid shell injection issues
                # and ensure quoting is handled correctly by the shell=False default.
                # However, systemctl set-environment expects the value to be quoted
                # if it contains spaces or special characters, so we'll quote it.
                # For `systemctl set-environment`, it's common to pass the entire
                # "KEY=VALUE" string as a single argument.
                cmd = ["systemctl", "set-environment", f"{name}='{value}'"]
                logger.debug(f"Running: {' '.join(cmd)}")
                subprocess.run(cmd, check=True, text=True, capture_output=True)
                logger.info(f"Set SystemD environment variable: {name}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to set SystemD environment variable {name}: {e.stderr}")
                raise RuntimeError(f"SystemD command failed for {name}.") from e
            except FileNotFoundError:
                logger.error("systemctl command not found. Is SystemD installed and in PATH?")
                raise RuntimeError("systemctl command not found.")
            except Exception as e:
                logger.error(f"An unexpected error occurred while setting SystemD env for {name}: {e}")
                raise RuntimeError(f"Unexpected error setting SystemD env for {name}.") from e

    def _validate_envars_file(self, args: argparse.Namespace) -> None:
        """Validates the envars YAML file for common issues."""
        envars = EnVars(args.filename)
        envars.load() # Load to populate internal structures

        errors: List[str] = []

        # Validate general configuration
        if not envars.app:
            errors.append("Configuration missing 'APP' field.")
        if not envars.kms_key_arn:
            errors.append("Configuration missing 'KMS_KEY_ARN' field.")
        if not envars.envs:
            errors.append("Configuration missing 'ENVIRONMENTS' field or it's empty.")

        # Validate individual environment variables
        for var in envars.envars:
            if not var.name.isupper():
                errors.append(f'Variable name "{var.name}" is not uppercase.')

            for env_key, env_val in var.envs.items():
                if env_key == 'description':
                    continue # Skip description field for environment validation

                if env_key not in envars.envs and env_key != 'default':
                    errors.append(f'Variable "{var.name}" has unknown environment "{env_key}".')

                if isinstance(env_val, str) and not env_val:
                    errors.append(f'Variable "{var.name}" in environment "{env_key}" has an unsupported empty string value.')
                elif isinstance(env_val, dict):
                    for account_key, account_val in env_val.items():
                        if account_key not in ['master', 'sandbox']:
                            errors.append(f'Variable "{var.name}" in env "{env_key}" has invalid account "{account_key}". Must be "master" or "sandbox".')
                        if isinstance(account_val, str) and not account_val:
                            errors.append(f'Variable "{var.name}" in env "{env_key}" account "{account_key}" has an unsupported empty string value.')

        if errors:
            logger.error(f"Validation failed for {args.filename}:")
            for error in errors:
                print(f'- {error}', file=sys.stderr)
            sys.exit(1)
        else:
            logger.info(f"Validation successful for {args.filename}.")
            print(f"Validation successful for {args.filename}.")

    def _flatten_template_vars(self, nested_list: List[List[str]]) -> List[str]:
        """Flattens a list of lists into a single list."""
        return [item for sublist in nested_list for item in sublist]

    def _get_aws_account(self) -> str:
        """
        Retrieves the AWS account ID and maps it to 'master' or 'sandbox'.
        """
        try:
            sts_client = boto3.client('sts')
            account_id = sts_client.get_caller_identity()['Account']
            if account_id == '511042647617':
                return 'master'
            elif account_id == '253613363555':
                return 'sandbox'
            else:
                logger.warning(f"Unknown AWS account ID: {account_id}. Returning it as is.")
                return account_id
        except (boto3.exceptions.ClientError, NoCredentialsError, ProfileNotFound) as e:
            logger.error(f"Failed to get AWS account ID: {e}. Please ensure AWS credentials are configured.")
            raise RuntimeError("Could not determine AWS account.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while getting AWS account: {e}")
            raise RuntimeError("Unexpected error getting AWS account.") from e


def main() -> None:
    """Main entry point for the CLI application."""
    cli = EnvarsCLI()
    cli.run()

if __name__ == '__main__':
    main()


