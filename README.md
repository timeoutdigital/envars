# envars

Command-line Python application to manage environment variables and AWS KMS encrypted secrets in a single file.

## Requirements

A KMS key should be created in your AWS account.

further reading at https://docs.aws.amazon.com/kms/latest/developerguide/create-keys.html

## Install

```
$ pip install git+https://github.com/timeoutdigital/envars@0.6
```

I may publish to pypi at a later date but sadly the `envars` name is already taken.

## Local Development

Clone

```
$ git clone git@github.com:timeoutdigital/envars.git
$ cd envars
```

Initialise

Install [Timeout Tools](https://github.com/timeoutdigital/timeout-tools/blob/master/README.md)

the run

```
timeout-tools python-setup
```

Test

```
$ invoke test
```

Run

```
$ python -m envars.envars
```

To list invoke options

```
invoke --list
```

## Usage

To create an envars.yml file

```
$ envars init --app myapp --environments prod,staging --kms-key-arn <your-arn>
```

Add a variable default value

```
$ envars add MYVAR=myvalue
```

Add a environment specific variable

```
$ envars add --env prod MYVAR=myprodvalue
```
Add a secret

```
$ envars add --secret MYSECRET=ssssshh
```

To print the variables for a specific environment

```
$ envars print --decrypt --env prod
```

Loading a var from parameter store at runtime
---------------------------------------------

```
MY_SPECIAL_VAR:
  default: parameter_store:/path/VAR
```

At runtime the value of `MY_SPECIAL_VAR` will be replaced with the value from parameter store
