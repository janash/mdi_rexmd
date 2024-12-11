#!/bin/bash

# Check if config file exists
if [ "$#" -ne 1 ]; then
    echo "Usage: setup_repex.sh config.txt"
    echo "Please provide a config file with:"
    echo "  temperatures=300,305,308,312"
    echo "  n_steps=100000"
    echo "  interval=1000"
    echo "  engine_image=/path/to/engine.sif"
    echo "  driver_image=/path/to/driver.sif"
    echo "  tinker_key=/path/to/tinker.key"
    echo "  tinker_xyz=/path/to/tinker.xyz"
    echo "  tinker_prm=/path/to/amoebabio18.prm"
    echo "  [Optional] equil=1000"
    exit 1
fi

# Load the config file
config_file=$1
if [ ! -f "$config_file" ]; then
    echo "Error: Config file '$config_file' not found"
    exit 1
fi

# Source the config file, ensuring syntax is valid
if ! source <(grep = "$config_file" | sed 's/ *= */=/g'); then
    echo "Error: Failed to parse configuration file '$config_file'."
    echo "Hint: Ensure the file has valid key=value pairs with no spaces around '='."
    exit 1
fi

# Check for required files and variables
required_vars=("tinker_key" "tinker_xyz" "tinker_prm")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Required configuration variable '$var' is missing or empty in '$config_file'."
        exit 1
    fi
done

for file in "$tinker_key" "$tinker_xyz" "$tinker_prm"; do
    if [ ! -f "$file" ]; then
        echo "Error: Required file '$file' not found."
        exit 1
    fi
done

# Check for Apptainer
if ! command -v apptainer &> /dev/null; then
    echo "Error: Apptainer is not installed or not in your PATH."
    exit 1
fi

# Proceed with the rest of the script...
IFS=',' read -ra temperatures <<< "$temperatures"
equil=${equil:-0}  # Default equilibration steps to 0 if not provided

output_file="run_repex.sh"
cat << EOF > "$output_file"
#!/bin/bash -l
EOF

# Generate the driver launch script
cat << 'EOF' > "launch_driver.sh"
#!/bin/bash

# Adjust to include the path to the container's Python
export PATH=/opt/venv/bin:$PATH

EOF

cat << EOF >> "launch_driver.sh"
mdi_rexmd -nsteps $n_steps -interval $interval -output_dir remd_analysis -mdi "-role DRIVER -name driver -method MPI"
EOF

chmod +x launch_driver.sh

# Step 1: Add equilibration steps if specified
if [ "$equil" -gt 0 ]; then
    echo "# Running equilibration steps" >> "$output_file"
    for temp in "${temperatures[@]}"; do
        equil_script="temp_tinker_launcher_equil_$temp.sh"
        cat << EOF > "$equil_script"
#!/bin/bash
mkdir -p tinker_${temp}
cp $tinker_xyz tinker_${temp}/tinker.xyz
cp $tinker_key tinker_${temp}/tinker.key
cp $tinker_prm tinker_${temp}/
cd tinker_${temp}

/repo/build/tinker9/build/tinker9 dynamic tinker.xyz $equil 1.0 0.1 4 $temp 1.0 -k tinker.key > tinker_${temp}_equil.log
sleep 1
EOF
        chmod +x "$equil_script"

        # Add the equilibration call to the output script
        echo "apptainer exec --nv $engine_image ./$equil_script &" >> "$output_file"
    done
    echo "wait" >> "$output_file"

    # Add REPEX steps
    cat << EOF >> "$output_file"

mpirun -np 1 \\
    apptainer exec $driver_image ./launch_driver.sh : \\
EOF

    for temp in "${temperatures[@]}"; do
        repex_script="temp_tinker_launcher_$temp.sh"
        cat << EOF > "$repex_script"
#!/bin/bash
cd tinker_${temp}
/repo/build/tinker9/build/tinker9 dynamic tinker.xyz $n_steps 1.0 0.1 4 $temp 1.0 -k tinker.key -mdi "-name TINKER_${temp} -role ENGINE -method MPI" > tinker_${temp}.log
EOF
        chmod +x "$repex_script"

        if [ "$temp" = "${temperatures[-1]}" ]; then
            echo "    apptainer exec --nv $engine_image ./$repex_script" >> "$output_file"
        else
            echo "    apptainer exec --nv $engine_image ./$repex_script : \\" >> "$output_file"
        fi
    done

else
    # Add REPEX steps without equilibration
    cat << EOF >> "$output_file"

mpirun -np 1 \\
    apptainer exec $driver_image ./launch_driver.sh : \\
EOF

    for temp in "${temperatures[@]}"; do
        repex_script="temp_tinker_launcher_$temp.sh"
        cat << EOF > "$repex_script"
#!/bin/bash
/repo/build/tinker9/build/tinker9 dynamic -k $tinker_key $tinker_xyz $n_steps 1.0 0.1 4 $temp 1.0 -mdi "-name TINKER_${temp} -role ENGINE -method MPI" > tinker_${temp}.log
EOF
        chmod +x "$repex_script"

        if [ "$temp" = "${temperatures[-1]}" ]; then
            echo "    apptainer exec --nv $engine_image ./$repex_script" >> "$output_file"
        else
            echo "    apptainer exec --nv $engine_image ./$repex_script : \\" >> "$output_file"
        fi
    done
fi

chmod +x "$output_file"
echo "Shell script '$output_file' has been generated successfully."