# envars

Command-line Python application to manage environment variables and AWS KMS encrypted secrets in a single file.

## Requirements

Your AWS account should have a KMS key created with an alias of `alias/envars`.

## Install

```
$ pip install git+ssh://git@github.com/timeoutdigital/envars
```

I may publish to pypi at a later date but sadly the `envars` name is already taken

## Usage

To create an envars.yml file

```
$ envars init --app myapp --environments prod,staging
```

Add a variable default value

```
$ envars add -var MYVAR=myvalue
```

Add a environment specific variable

```
$ envars add --secret --var MYSECRET=ssssshh
```

To print the variables for a specific environment 

```
$ envars print --decrypt --env prod
```
