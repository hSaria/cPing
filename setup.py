import os

from setuptools import find_packages, setup


def get_version():
    base_path = os.path.abspath(os.path.dirname(__file__))
    module_path = os.path.join(base_path, 'cping/__init__.py')

    with open(module_path, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            if line.startswith('__version__'):
                return line.split('"' if '"' in line else "'")[1]

        raise RuntimeError('Unable to find version string.')


def get_long_description():
    with open('README.md', 'r', encoding='utf-8') as file:
        return file.read()


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
    long_description=get_long_description(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    python_requires='>=3.6.0',
    url='https://github.com/hSaria/cPing',
    version=get_version(),
)
