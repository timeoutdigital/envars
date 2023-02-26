import logging

import jinja2
import yaml

from .kms import kms_agent

logging.getLogger("botocore.parsers").disabled = True
logging.getLogger("botocore.retryhandler").disabled = True
logging.getLogger("botocore.endpoint").disabled = True
logging.getLogger("botocore.httpsession").disabled = True
logging.getLogger("botocore.hooks").disabled = True
logging.getLogger("botocore.auth").disabled = True
logging.getLogger("botocore.credentials").disabled = True
logging.getLogger("botocore.utils").disabled = True
logging.getLogger("botocore.loaders").disabled = True
logging.getLogger("botocore.client").disabled = True
logging.getLogger("botocore.regions").disabled = True
logging.getLogger("urllib3.connectionpool").disabled = True


def get_loader():
    loader = yaml.SafeLoader
    loader.add_constructor(u'!secret', secret_constructor)
    return loader


class Secret():

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return self.value


def secret_representer(dumper, data):
    return dumper.represent_scalar(u'!secret', u'%s' % data, style='|')


yaml.add_representer(Secret, secret_representer)


def secret_constructor(loader, node: yaml.nodes.MappingNode) -> Secret:
    return Secret(loader.construct_scalar(node))


yaml.add_constructor(u'!secret', secret_constructor)


class EnVar:

    def __init__(self, name, envs, app, desc=None):
        logging.debug(f'EnVar init({name}, {envs}, {app}, {desc})')
        self.app = app
        self.desc = desc
        self.envs = envs
        if self.desc:
            self.envs['description'] = self.desc
        self.name = name

    def __repr__(self):
        return f"EnVar(name='{self.name}', envs={self.envs})"

    def get_value(self, env, account, decrypt=False):
        value = None
        if env in self.envs:
            if isinstance(self.envs[env], dict):
                if account in self.envs[env]:
                    value = self.decrypt(self.envs[env][account], env, account, decrypt)
            else:
                value = self.decrypt(self.envs[env], env, None, decrypt)
        if value is None and 'default' in self.envs:
            if isinstance(self.envs['default'], dict):
                if account in self.envs['default']:
                    value = self.decrypt(self.envs['default'][account], 'default', account, decrypt)
            else:
                value = self.decrypt(self.envs['default'], 'default', None, decrypt)
        return value

    def decrypt(self, value, env, account, decrypt):
        logging.debug(f'decrypt({value}, {env}, {account})')
        if decrypt and isinstance(value, Secret):
            encryption_context = {}
            encryption_context['app'] = self.app
            if env != 'default':
                encryption_context['env'] = env
            if account:
                encryption_context['account'] = account
            logging.debug(f'encryption_context({encryption_context})')
            value = kms_agent.decrypt(value.value, encryption_context)
        return value


class EnVars:

    def __init__(self, filename='envars.yml'):
        self.filename = filename
        self.app = None
        self.envs = []
        self.envars = []

    def load(self):
        with open(self.filename, "rb") as envars_yml:
            envars_file = yaml.load(envars_yml, Loader=get_loader())

        config = envars_file["configuration"]
        self.app = config['APP']
        self.envs = config['ENVIRONMENTS']
        for var in envars_file['environment_variables']:
            desc = None
            if 'description' in envars_file['environment_variables'][var]:
                desc = envars_file['environment_variables'][var]['description']
            self.envars.append(EnVar(var, envars_file['environment_variables'][var], self.app, desc=desc))

    def save(self):
        data = {}
        data['configuration'] = {}
        data['configuration']['APP'] = self.app
        data['configuration']['ENVIRONMENTS'] = self.envs
        data['environment_variables'] = self.build_yaml()
        with open(self.filename, "w") as envars_yml:
            yaml.dump(data, envars_yml, default_flow_style=False)

    def add(self, name, value, env_name='default', account=None, desc=None, is_secret=False):
        logging.debug(f'add({name}, {value}, {desc})')

        if env_name != 'default':
            if env_name not in self.envs:
                raise(Exception(f'Unknown Env: "{env_name}"'))

        if account and account not in ['master', 'sandbox']:
            raise(Exception(f'Unknown Account: {account}'))

        if is_secret:
            encryption_context = {}
            encryption_context['app'] = self.app
            if env_name != 'default':
                encryption_context['env'] = env_name
            if account:
                encryption_context['account'] = account
            logging.debug(f'encryption_context({encryption_context})')
            value = Secret(kms_agent.encrypt(value, encryption_context))

        if account:
            logging.debug('createing account var')
            for var in self.envars:
                if var.name == name:
                    if env_name not in var.envs:
                        var.envs[env_name] = {}
                    if isinstance(var.envs[env_name], str):
                        var.envs[env_name] = {}
                    var.envs[env_name][account] = value
                    if desc:
                        var.envs['description'] = desc
                    return

            self.envars.append(EnVar(
                name,
                {env_name: {account: value}},
                app=self.app,
                desc=desc,
            ))
        else:
            logging.debug('createing env var')
            for var in self.envars:
                if var.name == name:
                    var.envs[env_name] = value
                    if desc:
                        var.envs['description'] = desc
                    return

            self.envars.append(EnVar(
                name,
                {env_name: value},
                app=self.app,
                desc=desc,
            ))

    def build_yaml(self, decrypt=False):
        envars = {}
        for var in self.envars:
            envars[var.name] = var.envs
        return envars

    def build_env(self, env, account, decrypt=False):
        logging.debug(f'build_env({env}, {account})')
        envars = {}
        if env != 'default' and env not in self.envs:
            raise(Exception(f'Unknown Env: "{env}"'))

        # fetch all the non secret values
        for v in self.envars:
            value = v.get_value(env, account)
            if value and not isinstance(value, Secret):
                envars[v.name] = value

        jenv = jinja2.Environment()

        # process jinja templates
        for var in envars:
            envars[var] = jenv.from_string(envars[var]).render(envars)

        # fetch secrets
        for v in self.envars:
            value = v.get_value(env, account, decrypt)
            if value:
                if v.name not in envars:
                    envars[v.name] = value

        return envars

    def build(self, account, decrypt=False):
        logging.debug(f'build({account}, {decrypt})')
        envars = {}
        for v in self.envars:
            envars[v.name] = v.envs

        return envars

    def print(self, account, env=None, decrypt=False):
        logging.debug(f'print({account}, {env}, {decrypt})')
        print(yaml.dump(self.build(account, decrypt)))
