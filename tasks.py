from invoke import task


@task
def test(c):
    """Execute pytest"""
    c.run('pytest -v', pty=True)
