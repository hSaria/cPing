from setuptools import setup

REQUIRES_PYTHON = '>=3.6.0'

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='cping',
    author='hSaria',
    author_email='ping@heysaria.com',
    classifiers=[
        'Intended Audience :: System Administrators',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3', 'Topic :: Internet',
        'Topic :: System :: Networking :: Monitoring'
    ],
    description='Concurrent multi-host ping (ICMP and TCP)',
    license='MIT',
    long_description=long_description,
    long_description_content_type='text/markdown',
    python_requires=REQUIRES_PYTHON,
    scripts=['cping'],
    url='https://github.com/hSaria/cPing',
    version='0.0.3',
)
