from invoke import task

APP_NAME = 'envars'


@task
def test(c):
    """Execute pytest"""
    c.run('pytest -v', pty=True)
