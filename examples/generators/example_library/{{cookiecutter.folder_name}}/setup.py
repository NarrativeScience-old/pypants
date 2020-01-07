import setuptools

setuptools.setup(
    name="{{ cookiecutter.package_name }}",
    version="0.0.1",
    package_dir={"": "src"},
    packages=setuptools.find_packages("src"),
    provides=setuptools.find_packages("src"),
)
