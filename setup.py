from setuptools import setup, find_packages

setup(
    name="pop-llm",
    version="0.1",
    packages=find_packages(),
    description="A short description of your project",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    install_requires=[line.strip() for line in open('requirements.txt')],
    url='https://github.com/Microwave-WYB/POP',
    author="Yibo Wei",
    author_email="david_wyb2001@outlook.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
)
