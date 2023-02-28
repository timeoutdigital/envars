# envars

Command-line Python application to manage environment variables and AWS KMS encrypted secrets in a single file.

## Install

```
$ pip install git+ssh://git@github.com/timeoutdigital/envars
```

I may publish to pypi at a later date but sadly the `envars` name is already taken

## Local Development

Clone

```
$ git clone git@github.com:timeoutdigital/envars.git
$ cd envars
```

Initialise

```
$ make python
```

Test

```
$ make test
```

Run

```
$ python -m envars.envars
```

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
