from distutils.core import setup

package_version = '1.0.0'

setup(
    name='jetbrains-issues-dataset',
    packages=['jetbrains_issues_dataset',
              'jetbrains_issues_dataset.idea',
              'jetbrains_issues_dataset.youtrack_loader'],
    version=package_version,
    license='MIT',
    description='YouTrack data loader',
    author='Andrey Vokin',
    author_email='andrey.vokin@gmail.com',
    url='https://jetbrains.team/p/yh/repositories/youtrack-data-loader/',
    download_url=f'https://jetbrains.team/p/yh/packages/pypi/feedback-analysis-toolkit-package-repository/feedback-analysis-toolkit-package-repositoryjetbrains-issues-dataset/{package_version}/jetbrains-issues-dataset-{package_version}.tar.gz?download=true',
    keywords=[],
    install_requires=[
        'urllib3',
        'python-dateutil',
        'requests',
        'tqdm'
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'youtrack_downloader=jetbrains_issues_dataset.youtrack_loader.download_activities:main',
        ],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
