from setuptools import setup

setup(
    name="orchestrator_docker",
    version="0.1.0",
    author="Ramon Darwich de Menezes",
    description="Logs optional communication between servers",
    license="GNU",
    install_requires=["flask", "requests"],
    entry_points={
        "console_scripts": [
            # <Nome do Comando>=<Modulo (Arquivo)>:<Funcao>
            "run_log_server=server:main"
        ]
    }
)