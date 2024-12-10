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

# Check that required fields are present in the config file
required_vars=("tinker_key" "tinker_xyz" "tinker_prm")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Required configuration variable '$var' is missing or empty in '$config_file'."
        echo "Please ensure '$var' is specified with a valid file path."
        exit 1
    fi
done

# Check that required files exist
for file in "$tinker_key" "$tinker_xyz" "$tinker_prm"; do
    if [ ! -f "$file" ]; then
        echo "Error: Required file '$file' not found."
        echo "Hint: Ensure the file exists at the specified path and try again."
        exit 1
    fi
done

# Check for Apptainer
if ! command -v apptainer &> /dev/null; then
    echo "Error: Apptainer is not installed or not in your PATH."
    echo "Hint: Install Apptainer or add it to your PATH before running this script."
    exit 1
fi

# Proceed with the rest of the script...
echo "All required files and prerequisites are in place. Proceeding with setup..."

# Check for Apptainer
if ! command -v apptainer &> /dev/null; then
    echo "Error: Apptainer is not installed"
    exit 1
fi

# Read config file
config_file=$1
if [ ! -f "$config_file" ]; then
    echo "Error: Config file $config_file not found"
    exit 1
fi

# Source the config file
source <(grep = "$config_file" | sed 's/ *= */=/g')

# Convert comma-separated temperatures to array
IFS=',' read -ra temperatures <<< "$temperatures"

# Create the output file
output_file="run_repex.sh"

# Create the driver launch script
cat << 'EOF' > "launch_driver.sh"
#!/bin/bash

# Adjust to include the path to the container's Python
export PATH=/opt/venv/bin:$PATH

EOF

cat << EOF >> "launch_driver.sh"
mdi_rexmd -nsteps $n_steps -interval $interval -output_dir remd_analysis -mdi "-role DRIVER -name driver -method MPI"
EOF

chmod +x launch_driver.sh

# Start the launch script
cat << EOF > "$output_file"
#!/bin/bash -l

mpirun -np 1 \\
    apptainer exec $driver_image ./launch_driver.sh : \\
EOF

# Append mpirun commands for each temperature
for temp in "${temperatures[@]}"; do
    echo "Generating launcher script for temperature $temp..."

    # Create a temporary launcher script for Tinker
    cat << EOF > temp_tinker_launcher_$temp.sh
    #!/bin/bash
    mkdir -p tinker_${temp}
    cp tinker.xyz tinker_${temp}
    cp tinker.key tinker_${temp}
    cp amoebabio18.prm tinker_${temp}
    cd tinker_${temp}
    /repo/build/tinker9/build/tinker9 dynamic tinker.xyz $n_steps 1.0 0.1 4 $temp 1.0 -k tinker.key -mdi "-name TINKER_${temp} -role ENGINE -method MPI" > tinker_${temp}.log
EOF

    chmod +x temp_tinker_launcher_$temp.sh

    if [ "$temp" = "${temperatures[-1]}" ]; then
        echo "    apptainer exec --nv $engine_image ./temp_tinker_launcher_$temp.sh" >> "$output_file"
    else
        echo "    apptainer exec --nv $engine_image ./temp_tinker_launcher_$temp.sh : \\" >> "$output_file"
    fi
done

chmod +x "$output_file"
echo "Shell script '$output_file' has been generated successfully."