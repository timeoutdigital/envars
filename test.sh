#!/bin/bash

CMD="python -m envars.envars"

$CMD

$CMD -f /tmp/test.yml init -a testapp -e prod,staging

$CMD -f /tmp/test.yml add -v DFTTEST=dfttest
$CMD -f /tmp/test.yml add -v DFTTEST=dfttest -e prod
$CMD -f /tmp/test.yml add -v DFTTEST=dfttest -e prod -a master

$CMD -f /tmp/test.yml add -v ENVTEST=envtest -e prod
$CMD -f /tmp/test.yml add -v ENVTEST=envtest -e staging

$CMD -f /tmp/test.yml add -v ACCTEST=acctest -e prod -a master
$CMD -f /tmp/test.yml add -v ACCTEST=acctest -e prod -a sandbox -s

$CMD -f /tmp/test.yml add -v DOMAIN=timeout.com -a master
$CMD -f /tmp/test.yml add -v DOMAIN=sandbox.timeout.com -a sandbox

$CMD -f /tmp/test.yml add -v HOSTNAME="test.{{ DOMAIN }}"

$CMD -f /tmp/test.yml add -v SECTEST=prod-sectest -e prod -s
$CMD -f /tmp/test.yml add -v SECTEST=master-staging-sectest -e staging -a master -s

cat /tmp/test.yml

$CMD -f /tmp/test.yml print -e prod -d
$CMD -f /tmp/test.yml print -e staging -a master -d
