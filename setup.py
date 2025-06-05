from setuptools import setup, find_packages

setup(
    name='ttiny',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[],
    entry_points={
        'console_scripts': [
            'ttiny=ttiny.ttiny:run_ttiny',
        ],
    },
    author='displaynameishere',
    description='ttiny is a lightweight TUI mode-based text editor for files of all kinds',
    python_requires='>=3.6',
    long_description=open("README.md").read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourname/ttiny',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Environment :: Console',
        'Operating System :: POSIX :: Linux',
    ],
)