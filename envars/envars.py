#!/usr/bin/env python3
import argparse
import logging
import os
import re
import subprocess
import sys

import boto3
import yaml

from .models import EnVars

try:
    from collections.abc import Iterable
except ImportError:
    from collections import Iterable


def main():

    parser = argparse.ArgumentParser(
        description='Environment Management',
    )
    parser.add_argument(
        '-f',
        '--filename',
        default='envars.yml',
    )
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
    )

    subparsers = parser.add_subparsers(
        title="commands",
    )

    #
    # init envar subparser
    #
    parser_init = subparsers.add_parser(
        'init',
        help='initalise envar file',
    )
    parser_init.add_argument(
        '-a',
        '--app',
        required=True,
    )
    parser_init.add_argument(
        '-e',
        '--environments',
        required=True,
    )
    parser_init.add_argument(
        '-k',
        '--kms-key-arn',
        required=True,
    )
    parser_init.set_defaults(func=init)

    #
    # add envar subparser
    #
    parser_add = subparsers.add_parser(
        'add',
        help='add variable to envars file',
    )
    parser_add.add_argument(
        '-a',
        '--account',
        required=False,
        default=None,
    )
    parser_add.add_argument(
        '-d',
        '--desc',
        required=False,
    )
    parser_add.add_argument(
        '-e',
        '--env',
        required=False,
        default='default',
    )
    parser_add.add_argument(
        '-s',
        '--secret',
        required=False,
        action='store_true',
    )
    parser_add.add_argument(
        'variable',
    )
    parser_add.set_defaults(func=add_var)

    #
    # print env subparser
    #
    parser_print = subparsers.add_parser(
        'print',
        help='print environment variables from envars file',
    )
    parser_print.add_argument(
        '-a',
        '--account',
        required=False,
        default=None,
    )
    parser_print.add_argument(
        '-d',
        '--decrypt',
        required=False,
        action='store_true',
    )
    parser_print.add_argument(
        '-n',
        '--no-templating',
        required=False,
        default=False,
        action='store_true',
    )
    parser_print.add_argument(
        '-e',
        '--env',
        required=False,
    )
    parser_print.add_argument(
        '-t',
        '--template-var',
        required=False,
        nargs='+',
        action='append',
        default=[],
    )
    parser_print.add_argument(
        '-v',
        '--var',
        required=False,
        default=None,
    )
    parser_print.add_argument(
        '-y',
        '--yaml',
        required=False,
        action='store_true',
    )
    parser_print.add_argument(
        '-q',
        '--quote',
        required=False,
        default=False,
        action='store_true',
    )
    parser_print.add_argument(
        '-S',
        '--secrets_only',
        required=False,
        default=False,
        action='store_true',
    )
    parser_print.set_defaults(func=print_env)

    #
    # execute subparser
    #
    parser_exec = subparsers.add_parser(
        'exec',
        help='execute command with variables set',
    )
    parser_exec.add_argument(
        '-e',
        '--env',
        required=False,
    )
    parser_exec.add_argument(
        '-v',
        '--var',
        required=False,
        default=None,
    )
    parser_exec.add_argument(
        '-a',
        '--account',
        required=False,
        default=None,
    )
    parser_exec.add_argument(
        '-t',
        '--template-var',
        required=False,
        nargs='+',
        action='append',
        default=[],
    )
    parser_exec.add_argument('command', nargs=argparse.REMAINDER)
    parser_exec.set_defaults(func=execute)

    #
    # set_systemd_env subparser
    #
    parser_set_systemd_env = subparsers.add_parser(
        'set-systemd-env',
        help='execute command with variables set',
    )
    parser_set_systemd_env.add_argument(
        '-e',
        '--env',
        required=False,
    )
    parser_set_systemd_env.add_argument(
        '-v',
        '--var',
        required=False,
        default=None,
    )
    parser_set_systemd_env.add_argument(
        '-a',
        '--account',
        required=False,
        default=None,
    )
    parser_set_systemd_env.add_argument(
        '-t',
        '--template-var',
        required=False,
        nargs='+',
        action='append',
        default=[],
    )
    parser_set_systemd_env.set_defaults(func=set_systemd_env)

    #
    # validate subparser
    #
    parser_validate = subparsers.add_parser(
        'validate',
        help='validate envars file',
    )
    parser_validate.set_defaults(func=validate)

    args = parser.parse_args()
    if len(vars(args)) == 2:
        parser.print_help()
        sys.exit(0)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    args.func(args)


def set_systemd_env(args):
    args.yaml = False
    args.decrypt = True
    args.quote = False
    if not args.env:
        args.env = os.environ.get('STAGE')
    if not args.env:
        print('STAGE=<env> or -e <env> must be supplied')
        sys.exit(1)
    if 'RELEASE_SHA' in os.environ:
        args.template_var = [f'RELEASE={os.environ.get("RELEASE_SHA")}']
    args.var = None
    ret = process(
        args.filename,
        args.account,
        args.env,
        args.var,
        args.template_var,
        args.decrypt,
        True if args.no_templating is False else False,
        args.yaml,
        args.quote,
    )
    for val in ret:
        parts = val.split("=", 1)
        subprocess.run(
            f"systemctl set-environment {parts[0]}='{parts[1]}'",
            shell=True,
        )


def execute(args):
    command = args.command
    args.yaml = False
    args.decrypt = True
    args.quote = False
    if not args.env:
        args.env = os.environ.get('STAGE')
    if not args.env:
        print('STAGE=<env> or -e <env> must be supplied')
        sys.exit(1)
    if 'RELEASE_SHA' in os.environ:
        args.template_var = [f'RELEASE={os.environ.get("RELEASE_SHA")}']

    vals = {}
    if args.var:
        envars = EnVars(args.filename)
        envars.load()
        vals = envars.get_var(args.var, args.env, args.account)
    else:
        args.var = None
        ret = process(
            args.filename,
            args.account,
            args.env,
            args.var,
            args.template_var,
            args.decrypt,
            True if args.no_templating is False else False,
            args.yaml,
            args.quote,
        )
        for val in ret:
            parts = val.split("=", 1)
            vals[parts[0]] = parts[1]

    os.environ.update(vals)
    os.execlp(command[0], *command)


def validate(args):
    envars = EnVars(args.filename)
    envars.load()
    errors = []
    for var in envars.envars:
        if not var.name.isupper():
            errors.append(f'var name "{var.name}" is not uppercase')

        for env in var.envs:
            if env in ['default', 'description']:
                pass
            elif env not in envars.envs:
                errors.append(f'"{var.name}" has unknown env "{env}"')

            if var.envs[env] == '':
                errors.append(f'"{var.name}" "{env}" has unsupported empty string')

            if isinstance(var.envs[env], dict):
                for account in var.envs[env]:
                    if account not in ['master', 'sandbox']:
                        errors.append(f'"{var.name}" "{env}" has invalid account "{account}"')

                    if var.envs[env][account] == '':
                        errors.append(f'"{var.name}" "{env}" "{account}" has unsupported empty string')

    if errors:
        for error in errors:
            print(f'Error in devops/env_vars.yml: {error}')
        sys.exit(1)


def init(args):
    envars = EnVars(args.filename)
    envars.app = args.app
    envars.kms_key_arn = args.kms_key_arn
    envars.envs = args.environments.split(',')
    envars.save()


def add_var(args):
    matches = re.match(r'^([A-Z][A-Z|0-9|_]+)=(.*)$', args.variable)
    if not matches:
        raise (Exception('"VAR_NAME=value" expected'))
    name = matches.group(1)
    value = matches.group(2)
    envars = EnVars(args.filename)
    envars.load()
    envars.add(
        name,
        value,
        args.env,
        account=args.account,
        desc=args.desc,
        is_secret=args.secret,
    )
    print(envars.print(args.account, env=args.env, var=name))
    envars.save()


def print_env(args):
    ret = process(
        args.filename,
        args.account,
        args.env,
        args.var,
        args.template_var,
        args.decrypt,
        True if args.no_templating is False else False,
        args.yaml,
        args.quote,
        args.secrets_only,
    )
    if isinstance(ret, list):
        for var in ret:
            print(var)
    else:
        print(ret)


def process(
        filename, account, env, var=None, template_var=None,
        decrypt=False, templating=True, as_yaml=False, quote=False, secrets_only=False):

    envars = EnVars(filename)
    envars.load()

    if account is None:
        account = get_account()
    else:
        account = account

    if env:
        template_vars = {}
        if template_var:
            for tvar in flatten(template_var):
                template_vars[tvar.split('=')[0]] = tvar.split('=')[1]

        if as_yaml:
            return (
                yaml.dump(
                    {'envars': envars.build_env(
                        env,
                        account,
                        decrypt=decrypt,
                        template_vars=template_vars,
                        templating=templating,
                        secrets_only=secrets_only,
                    )},
                    default_flow_style=False
                )
            )
        else:
            env_vars = []
            for name, value in envars.build_env(
                    env,
                    account,
                    decrypt=decrypt,
                    template_vars=template_vars,
                    secrets_only=secrets_only,
                    templating=templating).items():
                if quote:
                    env_vars.append(f"{name}='{value}'")
                else:
                    env_vars.append(f'{name}={value}')

            return env_vars
    else:
        if var:
            var = var.upper()
        return (envars.print(account, var=var, decrypt=decrypt))


def flatten(lis):
    for item in lis:
        if isinstance(item, Iterable) and not isinstance(item, str):
            for x in flatten(item):
                yield x
        else:
            yield item


def get_account():
    sts_client = boto3.client('sts')
    account = sts_client.get_caller_identity()['Account']
    if account == '511042647617':
        return 'master'
    elif account == '253613363555':
        return 'sandbox'


if __name__ == '__main__':
    main()
