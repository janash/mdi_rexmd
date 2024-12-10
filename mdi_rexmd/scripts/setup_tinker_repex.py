import os
import subprocess
import sys

def main():
    # Get the path of the current module
    module_path = os.path.dirname(os.path.realpath(__file__))

    # The script is in the same directory as the module
    script_path = os.path.join(module_path, "setup_tinker_repex.sh")

    result = subprocess.run(["bash", script_path] + sys.argv[1:], check=True)
    return result.returncode
