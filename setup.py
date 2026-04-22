from setuptools import setup, find_packages

setup(
    name="xinglian-ssl-client",
    version="1.0.0",
    description="星链下载SSL证书客户端 - 支持Windows/Linux/macOS",
    author="Cockleshell",
    author_email="support@cockleshell.cn",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.6",
    install_requires=[
        "requests",
        "pyyaml>=5.0",
        "rich>=10.0.0",
        "qrcode>=7.0.0",
    ],
    extras_require={
        "dev": ["pytest>=6.0.0", "pyinstaller>=5.0.0"],
    },
    entry_points={
        "console_scripts": [
            "xinglian-ssl=ssl_client.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Security",
        "Topic :: System :: Systems Administration",
    ],
)
