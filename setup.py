from setuptools import find_packages, setup

REQUIRES_PYTHON = '>=3.6.0'

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='cping',
    author='hSaria',
    author_email='sariahajjar@gmail.com',
    classifiers=[
        'Intended Audience :: System Administrators',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3', 'Topic :: Internet',
        'Topic :: System :: Networking :: Monitoring', 'Topic :: Utilities'
    ],
    description='Concurrent multi-host ping (ICMP and TCP)',
    entry_points={'console_scripts': ['cping = cping.__main__:main']},
    install_requires=['windows-curses; sys_platform == "win32"'],
    license='MIT',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(),
    python_requires=REQUIRES_PYTHON,
    url='https://github.com/hSaria/cPing',
    version='0.1.2',
)
