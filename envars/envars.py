#!/usr/bin/env python3
import argparse
import logging
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
        '-v',
        '--var',
        required=True,
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
    parser_print.set_defaults(func=print_env)

    #
    # execute subparser
    #
    parser_exec = subparsers.add_parser(
        'exec',
        help='execute command with variables set',
    )
    parser_exec.set_defaults(func=execute)

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


def execute():
    pass


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
    envars.envs = args.environments.split(',')
    envars.save()


def add_var(args):
    name = args.var.split('=')[0].upper()
    value = args.var.split('=')[1]
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
    envars.print(args.account, args.env, var=name)
    envars.save()


def print_env(args):
    envars = EnVars(args.filename)
    envars.load()

    if args.account is None:
        account = get_account()
    else:
        account = args.account

    if args.env:
        template_vars = {}
        for tvar in flatten(args.template_var):
            template_vars[tvar.split('=')[0]] = tvar.split('=')[1]

        if args.yaml:
            print(
                yaml.dump(
                    {'envars': envars.build_env(
                        args.env,
                        account,
                        decrypt=args.decrypt,
                        template_vars=template_vars,
                    )},
                    default_flow_style=False
                )
            )
        else:
            for name, value in envars.build_env(
                    args.env,
                    account,
                    decrypt=args.decrypt,
                    template_vars=template_vars).items():
                print(f'{name}={value}')
    else:
        var = None
        if args.var:
            var = args.var.upper()
        envars.print(account, var=var, decrypt=args.decrypt)


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
