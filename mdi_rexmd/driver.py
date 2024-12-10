import sys
import os
import warnings
import math
import random

import numpy as np

# Import the MDI Library
import mdi

# Import MPI Library
try:
    from mpi4py import MPI

    use_mpi4py = True
    mpi_comm_world = MPI.COMM_WORLD
except ImportError:
    use_mpi4py = False
    mpi_comm_world = None

# Import parser
from .util import create_parser, connect_to_engines_arbitrary

def exchange_states(engine1, engine2):

    engine1.node = "@COORDS"
    engine2.node = "@COORDS"

    coords1 = np.array(engine1.coords) # q[i]
    coords2 = np.array(engine2.coords) # q[j]

    velocities1 = np.array(engine1.velocities) # p[i]
    velocities2 = np.array(engine2.velocities) # p[j]

    # calculate the velocity scaling factor
    t_scale = math.sqrt(engine2.temperature / engine1.temperature) # Tn / Tm

    # scale the velocities
    # Based on Sugita and Okamoto, Chem Phys Leters, 1999
    velocities1 = velocities1 * t_scale  # p[i]'
    velocities2 = velocities2 / t_scale  # p[j]'

    engine1.velocities = velocities2 # setting p[i] = p[j]'
    engine2.velocities = velocities1 # setting p[j] = p[i]'

    engine1.coords = coords2 # setting q[i] = q[j]
    engine2.coords = coords1 # setting q[j] = q[i]

    print(f"Exchanged states between {engine1.engine_name} and {engine2.engine_name}")

def main():
    # Read in the command-line options
    args = create_parser().parse_args()

    mdi_options = args.mdi

    print(f"MDI options: {mdi_options}")

    if mdi_options is None:
        mdi_options = (
            "-role DRIVER -name driver -method TCP -port 8021 -hostname localhost"
        )
        warnings.warn(f"Warning: -mdi not provided. Using default value: {mdi_options}")

    interval = args.interval
    num_steps = args.nsteps
    analysis_dir = args.output_dir

    # Make sure the analysis directory exists
    if not os.path.exists(analysis_dir):
        os.makedirs(analysis_dir)

    # Open a log file
    f = open(os.path.join(analysis_dir, "driver.log"), "w+")

    # Initialize the MDI Library
    mdi.MDI_Init(mdi_options)

    # Get the correct MPI intra-communicator for this code
    mpi_comm_world = mdi.MDI_MPI_get_world_comm()

    engines = connect_to_engines_arbitrary()
    
    natoms_list = [ engine.natoms for engine in engines ]
    
    # Check that the number of atoms is the same for all engines
    if len(set(natoms_list)) != 1:
        raise ValueError("The number of atoms is not the same for all engines.")
    else:
        natoms = natoms_list[0] 

    # Initialize empty lists for even and odd indexed pairs
    # Approach adopted by Gromacs
    even_pairs = []
    odd_pairs = []

    # Loop over the indices to get engine pairs for exchange
    for i in range(0, len(engines), 2):
        if i + 1 < len(engines):
            even_pairs.append((engines[i], engines[i+1]))

    for i in range(1, len(engines), 2):
        if i + 1 < len(engines):
            odd_pairs.append((engines[i], engines[i+1]))

    pairs = [ even_pairs, odd_pairs ]

    # Make a dictionary to store exchange statistics for each pair
    exchange_stats = {}

    for pair in even_pairs:
        exchange_stats[pair] = {
            "attempted": 0,
            "accepted": 0,
            "rejected": 0
        }

    for pair in odd_pairs:
        exchange_stats[pair] = {
            "attempted": 0,
            "accepted": 0,
            "rejected": 0
        }

    attempt_number = 1

    # Make a dictionary for tracking replicas
    # and inverse dictionary for looking up replica number
    replicas = {}
    inverse_replicas = {}
    for i in range(len(engines)):

        # Key is an integer - replica number
        replicas[i] = { "file_handle": open(os.path.join(analysis_dir, f"replica_{i}.csv"), "w+") }
        replicas[i]["file_handle"].write("Step,Temperature\n")
        replicas[i]["file_handle"].write(f"0,{engines[i].temperature}\n")

        # Key is the temperature, use to get replica number
        inverse_replicas[engines[i].temperature] = i

    ###########################
    # Perform the simulation
    ###########################

    # Replica Exchange MD.

    # We need to run the simulations for a period of time (interval),
    # check the energies, and exchange the configurations
    # if a criteria is met.

    # Procedure:

    # 1. Launch N simulations at different temperatures.
    # 2. Run the simulations for a period of time.
    # 3. Retrieve the energies and check the exchange criteria.
    # 4. If the criteria is met, exchange the configurations.

    for engine in engines:
        engine.node = "@INIT_MD"

    for step_num in range(1, num_steps+1):
        print(f"Step: {step_num}")  
        for engine in engines:
            engine.node = "@FORCES"

        if step_num % interval == 0:

            attempt_mod = attempt_number % 2
            attempt_number += 1

            attempt_pairs = pairs[attempt_mod]

            for pair in attempt_pairs:
                exchange_stats[pair]["attempted"] += 1
                delta_energy = pair[0].potential_energy - pair[1].potential_energy
                delta_beta = pair[0].beta - pair[1].beta

                print(f"Pair: {pair[0].engine_name} and {pair[1].engine_name}")
                print(f"Delta Energy: {delta_energy}")
                print(f"Delta Beta: {delta_beta}")

                exchange_prob = min(1, math.exp(delta_energy * delta_beta))

                if random.random() < exchange_prob:

                    # look up the replica indes
                    replica_1 = inverse_replicas[pair[0].temperature]
                    replica_2 = inverse_replicas[pair[1].temperature]

                    replicas[replica_1]["file_handle"].write(f"{step_num},{pair[1].temperature}\n") 
                    replicas[replica_2]["file_handle"].write(f"{step_num},{pair[0].temperature}\n")
                    

                    # update replica positions - switch
                    inverse_replicas[pair[0].temperature] = replica_2
                    inverse_replicas[pair[1].temperature] = replica_1

                    # perform the exchange
                    exchange_states(pair[1], pair[0])
                    exchange_stats[pair]["accepted"] += 1
                    
                    print(f"Exchange accepted between {pair[0].engine_name} and {pair[1].engine_name} at step {step_num}")
                    f.write(f"Exchange accepted between {pair[0].engine_name} and {pair[1].engine_name} at step {step_num}\n")
                    
                else:
                    exchange_stats[pair]["rejected"] += 1

    # Print acceptance rate for each pair
    total_number_of_attempts = 0
    total_number_of_accepted = 0

    f.close()

    for replica in replicas.values():
        replica["file_handle"].close()

    with open(os.path.join(analysis_dir, "exchange_stats.txt"), "w") as f:

        f.write("Temperature1,Temperature2,Accepted,Attempted,Acceptance Rate\n")

        for key, stats in exchange_stats.items():
            
            try:
                print(f"Pair: {key[0].temperature} and {key[1].temperature}\t{stats['accepted']}\t{stats['attempted']} \t{ stats['accepted'] / stats['attempted'] }")
                f.write(f"{key[0].temperature},{key[1].temperature},{stats['accepted']},{stats['attempted']},{ stats['accepted'] / stats['attempted'] }\n")
            
            except ZeroDivisionError:
                print(f"Pair: {key[0].engine_name} and {key[1].engine_name}\t 0.0")
            
            total_number_of_attempts += stats["attempted"]
            total_number_of_accepted += stats["accepted"]


    acceptance_rate = total_number_of_accepted / total_number_of_attempts
    print(f"Acceptance rate: {acceptance_rate}")
            
    # Send the "EXIT" command to each of the engines
    for engine in engines:
        engine.exit()

if __name__ == "__main__":

    main()
