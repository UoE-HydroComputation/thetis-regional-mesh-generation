"""Shared helpers for selecting and initialising a qmesh installation."""


def get_qmesh_module(version):
    """Return the requested qmesh module and initialise qmeshcontainers."""
    if version == "qmesh3":
        import qmesh3 as qmesh
    elif version == "qmeshcontainers":
        import qmesh

        qmesh.initialise()
    else:
        raise ValueError(
            "qmesh version must be 'qmesh3' or 'qmeshcontainers'"
        )
    return qmesh
