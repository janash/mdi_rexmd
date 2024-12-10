"""
Utility functions for the replica_exchange_py driver.
"""

import argparse
import time

import mdi

from .engine import MDIEngine


def create_parser():
    """Create the parser for the replica_exchange_py driver"""

    parser = argparse.ArgumentParser(description="replica_exchange_py Driver")

    parser.add_argument(
        "-mdi",
        help="flags for mdi.",
        default=None,
        type=str,
    )

    # add any additional arguments here

    parser.add_argument(
        "-nsteps",
        help="number of steps to run",
        default=10000,
        type=int,
    )

    parser.add_argument(
        "-interval",
        help="interval between exchange attempts",
        default=40,
        type=int,
    )

    parser.add_argument(
        "-output_dir",
        help="directory to store analysis files",
        default="analysis",
        type=str,
    )

    return parser

def connect_to_engines_object(nengines):

    engines = []
    for _ in range(nengines):
        comm = mdi.MDI_Accept_Communicator()

        # Check the name of the engine
        mdi.MDI_Send_Command("<NAME", comm)
        engine_name = mdi.MDI_Recv(mdi.MDI_NAME_LENGTH, mdi.MDI_CHAR, comm)

        engine = MDIEngine(engine_name, comm)

        engines.append(engine)

    # Sort the engines by temperature
    engines = sorted(engines, key=lambda x: x.temperature)

    return engines

def connect_to_engines_arbitrary(max_iter=1000):
    
    time.sleep(3) # wait for the engines to start

    engines = []

    flag = mdi.MDI_Check_for_communicator()

    for _ in range(max_iter):
        if flag != 1:
            break
        comm = mdi.MDI_Accept_Communicator()

        # Check the name of the engine
        mdi.MDI_Send_Command("<NAME", comm)
        engine_name = mdi.MDI_Recv(mdi.MDI_NAME_LENGTH, mdi.MDI_CHAR, comm)

        engine = MDIEngine(engine_name, comm)

        engines.append(engine)
        
        flag = mdi.MDI_Check_for_communicator()
    
    # Sort the engines by temperature
    engines = sorted(engines, key=lambda x: x.temperature)
    
    return engines

def connect_to_engines(nengines):
    """Connect to the engines.
    
    Parameters
    ----------
    nengines : int
        The number of engines to connect to.
    
    Returns
    -------
    dict
        A dictionary of engines. The keys corresponds to the engine names.
    """

    engines = {}
    for iengine in range(nengines):
        comm = mdi.MDI_Accept_Communicator()

        # Check the name of the engine
        mdi.MDI_Send_Command("<NAME", comm)
        engine_name = mdi.MDI_Recv(mdi.MDI_NAME_LENGTH, mdi.MDI_CHAR, comm)

        engines[engine_name] = comm

    return engines
        
